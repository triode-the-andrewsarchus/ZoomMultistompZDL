"""Offline fault tests: never opens MIDI/audio ports."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock

import mido
import numpy as np
from file_session import crc32_tail, pack7
from backup import CheckedInput
from audio import analyze, require_loopback


class BackupTests(unittest.TestCase):
    def packet(self, body, length=None):
        n = len(body) if length is None else length
        return mido.Message('sysex', data=[0x52, 0, 0x6e, 0x64, 0x12, 0, n & 127, n >> 7]
                            + list(pack7(body)) + list(crc32_tail(body)))

    def test_crc_and_length_are_required(self):
        body = b'PTCF\x80\xff' * 20
        port = Mock()
        port.poll.return_value = self.packet(body)
        self.assertEqual(CheckedInput(port).receive(), port.poll.return_value)
        port.poll.return_value = self.packet(body, len(body) - 1)
        with self.assertRaises(RuntimeError):
            CheckedInput(port).receive()
        bad = list(self.packet(body).data)
        bad[-2] ^= 1
        port.poll.return_value = mido.Message('sysex', data=bad)
        with self.assertRaises(RuntimeError):
            CheckedInput(port).receive()


class AudioTests(unittest.TestCase):
    def test_linearity_measurement_detects_a_saturated_output_stage(self):
        import soundfile as sf
        from analyze import validate_linearity
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wave = np.tile(np.linspace(-1, 1, 100, endpoint=False), 60)
            def recording(name, samples):
                path = root / name
                path.mkdir(exist_ok=True)
                sf.write(path / 'return.wav', np.repeat(samples[:, None], 2, axis=1), 1000, subtype='FLOAT')
            recording('baseline', np.zeros(len(wave)))
            for level in (1, 2, 5, 10, 25, 50, 75, 100):
                recording(f'peak{level:02}', wave*.55*level/100)
            rows, errors = validate_linearity(root)
            self.assertFalse(errors)
            self.assertEqual(len(rows), 8)
            recording('peak100', np.clip(wave*.55, -.3, .3))
            _, errors = validate_linearity(root)
            self.assertEqual(len(errors), 1)
            self.assertIn('level', errors[0])
            recording('peak01', np.zeros(len(wave)))
            _, errors = validate_linearity(root)
            self.assertIn('Quiet diagnostic amplitude is missing', errors[0])

    def test_harmonic_fit_resolves_weak_tones_at_arbitrary_window_phases(self):
        from reference import harmonic_rms
        rate, frequency = 48000, 997
        t = np.arange(int(.8 * rate)) / rate
        amplitudes = np.array([.4, .0006, .15, .0002, .017, .009, .004, .002, .001, .0005])
        for phase in (0, .41, 1.9):
            audio = .01 + sum(amplitude * np.sin(2*np.pi*frequency*harmonic*t + phase*harmonic)
                              for harmonic, amplitude in enumerate(amplitudes, 1))
            np.testing.assert_allclose(harmonic_rms(audio, rate, frequency), amplitudes/np.sqrt(2),
                                       atol=1e-12, rtol=1e-9)
        with self.assertRaises(ValueError):
            harmonic_rms(audio, rate, frequency, count=25)

    def test_loopback_health_rejects_finite_noise_and_wrong_channel_paths(self):
        report = dict(finite=True, clipped=False, xruns=[], paths=[])
        with self.assertRaises(RuntimeError):
            require_loopback(report)
        report['paths'] = [dict(send=ch, capture=ch, correlation=.95, gain_db=-20) for ch in range(2)]
        require_loopback(report)
        for field, value in [('correlation', .1), ('gain_db', -90), ('capture', 0)]:
            invalid = dict(report, paths=[dict(p) for p in report['paths']])
            invalid['paths'][1][field] = value
            with self.assertRaises(RuntimeError):
                require_loopback(invalid)

    def test_known_delay_gain_and_silence(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 0.01, (2000, 2))
        x[1000:, 0] = 0
        x[:1000, 1] = 0
        y = np.zeros_like(x)
        y[137:] = x[:-137] * 0.5
        result = analyze(x, y, 48000)
        for channel in range(2):
            path = next(p for p in result['paths'] if p['send'] == channel and p['capture'] == channel)
            self.assertEqual(path['latency_samples'], 137)
            self.assertAlmostEqual(path['gain_db'], -6.0205999, places=5)
        self.assertTrue(analyze(x, np.zeros_like(x), 48000)['silent'])
        y[0, 0] = 1
        self.assertTrue(analyze(x, y, 48000)['clipped'])


class AuditionSafetyTests(unittest.TestCase):
    def test_restoration_bypasses_before_replacing_the_experiment(self):
        from unittest.mock import patch
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.original = b'stock patch'
        session.restore_parameter_count = 0
        session.edit = Mock()
        session.current = Mock(return_value=b'stock patch')
        session.pedal = Mock()
        stock = Mock()
        effect = Mock(id=0x06000020, enabled=False)
        stock.EDTB.effects = [Mock(reversed=Mock(bitwise=effect))]
        with patch('audition.stock_patch', return_value=stock), patch('audition.ZPTC.parse', return_value=stock), \
                patch('audition.editor_off'), patch('audition.time.sleep') as settle:
            session.restore()
        self.assertEqual([call.args for call in session.edit.call_args_list][:2], [(0, 0), (1, 0x06000020)])
        settle.assert_called_once_with(.25)
        original_edits = session.edit.call_args_list[:]
        session.edit.reset_mock()
        observations = []
        with patch('audition.stock_patch', return_value=stock), patch('audition.ZPTC.parse', return_value=stock), \
                patch('audition.editor_off'), patch('audition.time.sleep'):
            session.restore(observations.append)
        self.assertEqual(session.edit.call_args_list, original_edits,
                         'Audio tracing must not add or reorder MIDI mutations')
        self.assertEqual(observations, ['bypass', 'stock-id', 'stock-settings', 'editor-off'])

    def test_forbidden_commands_cannot_reach_output(self):
        import io
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.log = io.StringIO()
        session.pedal = Mock()
        for command in [[0x52, 0, 0x6e, 0x5b], [0x52, 0, 0x6e, 0x28],
                        [0x52, 0, 0x6e, 0x01], [0x52, 0, 0x6e, 0x60, 0x24]]:
            with self.assertRaises(ValueError):
                session.transmit_sysex(command)
        session.pedal.outport.send.assert_not_called()

    def test_edit_failure_prevents_automatic_cleanup_edits(self):
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.protocol_ok = True
        session._edit_checked = Mock(side_effect=RuntimeError('bad reply'))
        with self.assertRaises(RuntimeError):
            session.edit(2, 50)
        self.assertFalse(session.protocol_ok)

    def test_known_notifications_drain_but_errors_stop(self):
        import io
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.log = io.StringIO()
        session.pedal = Mock()
        session.pedal.inport.poll.side_effect = [mido.Message('sysex', data=[0x52, 0, 0x6e, 0x64, 0x20, 1]), None]
        session.drain()
        session.pedal.inport.poll.side_effect = [mido.Message('sysex', data=[0x52, 0, 0x6e, 0, 1])]
        with self.assertRaises(RuntimeError):
            session.drain()


class CampaignSafetyTests(unittest.TestCase):
    def test_retained_set_requires_complete_current_passing_evidence(self):
        import hashlib
        import json
        from unittest.mock import patch
        import install_set
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'src/msplus/test'
            (folder / 'build').mkdir(parents=True)
            manifest = folder / 'manifest.json'
            manifest.write_text(json.dumps(dict(filename='XXTEST', kernel='test.c')))
            source = folder / 'test.c'
            source.write_text('original source')
            artifact = folder / 'build/XXTEST.ZD2'
            artifact.write_bytes(b'tested binary')
            (folder / 'build/REPORT.md').write_text('validated')
            hil = root / 'hil'
            (hil / 'baseline').mkdir(parents=True)
            (hil / 'baseline/report.json').write_text(json.dumps(dict(finite=True, clipped=False, xruns=[],
                paths=[dict(send=ch, capture=ch, gain_db=-20, correlation=.95) for ch in range(2)])))
            (hil / 'BUILT.ZD2').write_bytes(artifact.read_bytes())
            (hil / 'SOURCES.json').write_text(json.dumps({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                         for p in (source, manifest)}))
            evidence = hil / 'analysis.json'
            (hil / 'restored').mkdir()
            restored = hil / 'restored/report.json'
            restored.write_bytes((hil / 'baseline/report.json').read_bytes())
            recording = restored.with_name('return.wav')
            recording.write_bytes(b'restored audio')
            proof = json.dumps(dict(report='restored/report.json',
                report_sha256=hashlib.sha256(restored.read_bytes()).hexdigest(),
                return_sha256=hashlib.sha256(recording.read_bytes()).hexdigest()))
            (hil / 'AUDIO_RESTORED').write_text(proof)
            analysis = dict(passed=True, errors=[], checks=['capture_integrity', 'signal_above_noise', 'zero_input_stability'])
            evidence.write_text(json.dumps(analysis))
            row = dict(port='test', evidence='hil/analysis.json', tested_binary_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
            report = dict(ports=[row])
            with patch.object(install_set, 'ROOT', root):
                self.assertEqual(install_set.qualified_artifacts(report), dict(test=artifact))
                for rows in ([], [row, row]):
                    with self.assertRaisesRegex(RuntimeError, 'complete musical set'):
                        install_set.qualified_artifacts(dict(ports=rows))
                for invalid in (dict(analysis, passed=False), dict(analysis, checks=[])):
                    evidence.write_text(json.dumps(invalid))
                    with self.assertRaises(RuntimeError):
                        install_set.qualified_artifacts(report)
                evidence.write_text(json.dumps(analysis))
                (hil / 'AUDIO_RESTORED').unlink()
                with self.assertRaisesRegex(RuntimeError, 'stock-audio restoration'):
                    install_set.qualified_artifacts(report)
                (hil / 'AUDIO_RESTORED').write_text(proof)
                recording.write_bytes(b'changed recording')
                with self.assertRaisesRegex(RuntimeError, 'restoration recording changed'):
                    install_set.qualified_artifacts(report)
                recording.write_bytes(b'restored audio')
                artifact.write_bytes(b'untested rebuild')
                with self.assertRaisesRegex(RuntimeError, 'tested binary'):
                    install_set.qualified_artifacts(report)
                artifact.write_bytes(b'tested binary')
                source.write_text('untested source change')
                with self.assertRaisesRegex(RuntimeError, 'source has changed'):
                    install_set.qualified_artifacts(report)

    def test_retained_set_stops_on_uncertain_install_without_rollback(self):
        from unittest.mock import patch
        import install_set
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / 'evidence.json'
            evidence.write_text('{}')
            argv = ['install_set.py', '--backup', str(root / 'backup'), '--evidence', str(evidence),
                    '--output', str(root / 'output')]
            with patch.object(install_set.sys, 'argv', argv), \
                    patch.object(install_set, 'qualified_artifacts', return_value={'test': root / 'XXTEST.ZD2'}), \
                    patch.object(install_set, 'verify_backup'), patch.object(install_set, 'preflight'), \
                    patch.object(install_set, 'upstream_operation', side_effect=[None, RuntimeError('uncertain transfer')]) as operation, \
                    patch.object(install_set.subprocess, 'run') as audit:
                with self.assertRaisesRegex(RuntimeError, 'uncertain transfer'):
                    install_set.main()
                self.assertEqual([c.args[1] for c in operation.call_args_list], ['install', 'install'])
                audit.assert_not_called()

    def test_missing_audio_restoration_marker_stops_before_uninstall(self):
        import json
        from unittest.mock import patch
        import run
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            effect = root / 'src/msplus/test'
            (effect / 'build').mkdir(parents=True)
            (effect / 'manifest.json').write_text(json.dumps(dict(filename='XXTEST')))
            (effect / 'build/XXTEST.ZD2').write_bytes(b'test')
            (effect / 'build/REPORT.md').write_text('test')
            output = root / 'campaign'
            def metadata_only(*args, **kwargs):
                (output / 'hil').mkdir()
                (output / 'hil/RESTORED').write_text('metadata only')
                return Mock(returncode=0)
            with patch.object(run, 'ROOT', root), patch.object(run, 'upstream_operation') as operation, \
                    patch.object(run.subprocess, 'run', side_effect=metadata_only):
                with self.assertRaisesRegex(RuntimeError, 'audio health unverified'):
                    run.run_effect('test', root / 'backup', output)
                self.assertEqual([c.args[1] for c in operation.call_args_list], ['install', 'install'])

    def test_final_catalogue_requires_exact_additions_and_preserves_factory_entries(self):
        from verify import check_catalogue
        from zoomzt2 import ZT2
        factory = dict(effect='FACTORY.ZD2', version='1.00', id=0x07000010, installed=1)
        custom = dict(effect='XXTEST.ZD2', version='0.10', id=0x07001100, installed=1)
        manifest = dict(filename='XXTEST', version='0.10', id='07001100')
        def catalogue(effects):
            return ZT2.build([dict(name='TEST'), [dict(group=7, groupname=7, effects=effects)]])
        original = catalogue([factory])
        check_catalogue(original, original, [])
        check_catalogue(original, catalogue([factory, custom]), [manifest])
        for effects in ([custom], [factory], [factory, custom, custom],
                        [dict(factory, installed=0), custom],
                        [factory, dict(custom, version='0.11')]):
            with self.assertRaises(RuntimeError):
                check_catalogue(original, catalogue(effects), [manifest])

    def test_final_readback_rejects_modified_custom_binary(self):
        import json
        from verify import check_files
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'test'
            (folder / 'build').mkdir(parents=True)
            path = folder / 'manifest.json'
            path.write_text(json.dumps(dict(filename='XXTEST')))
            (folder / 'build/XXTEST.ZD2').write_bytes(b'expected')
            (folder / 'build/XXTEST.ZIC').write_bytes(b'icon')
            session = Mock()
            session.download.side_effect = [b'expected', b'icon']
            absent, verified = check_files(session, [path], {'test'})
            self.assertFalse(absent)
            self.assertEqual(len(verified), 2)
            session.download.side_effect = [b'corrupt']
            with self.assertRaises(RuntimeError):
                check_files(session, [path], {'test'})

    def test_uncertain_install_stops_without_followup(self):
        from unittest.mock import patch
        from run import upstream_operation
        with tempfile.TemporaryDirectory() as tmp, patch('run.fcntl.flock'), patch('run.subprocess.run', return_value=Mock(returncode=4)) as execute:
            with self.assertRaises(RuntimeError):
                upstream_operation(Path(tmp), 'install', Path('XXTEST.ZD2'))
            self.assertEqual(execute.call_count, 1)
            self.assertIn('install', execute.call_args.args[0])

    def test_temp_volume_is_bounded_and_other_system_edits_refused(self):
        import io
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.log = io.StringIO()
        session.pedal = Mock()
        session.transmit_sysex([0x52, 0, 0x6e, 0x64, 0x20, 0, 0x64, 0, 10, 0, 0, 0, 0])
        for param in [0x0f, 0x08, 0x09]:
            with self.assertRaises(ValueError):
                session.transmit_sysex([0x52, 0, 0x6e, 0x64, 0x20, 0, 0x64, param, 1, 0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
