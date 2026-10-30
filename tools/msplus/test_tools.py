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


class ArtworkTests(unittest.TestCase):
    def test_original_art_crops_exclude_legacy_live_value_boxes(self):
        import hashlib
        import json
        import sys
        from PIL import Image
        from artwork import ROOT
        sys.path.insert(0, str(ROOT / 'build'))
        from decode_picture import decode_picture, read_image_info
        records = json.loads((ROOT / 'src/msplus/artwork/sources.json').read_text())
        self.assertEqual(len(records), 34)
        for name, record in records.items():
            with self.subTest(effect=name):
                source = ROOT / record['source']
                panel = ROOT / 'src/msplus/artwork' / (name + '.png')
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), record['source_sha256'])
                self.assertEqual(hashlib.sha256(panel.read_bytes()).hexdigest(), record['png_sha256'])
                x0, y0, x1, y1 = record['crop']
                self.assertEqual((x1-x0, y1-y0), (128, 36))
                for _, x, y in read_image_info(str(source))['knobs']:
                    self.assertTrue(y+15 <= y0 or y >= y1 or x+20 <= x0 or x >= x1,
                                    'Artwork must exclude old firmware value boxes')
                pixels, symbol = decode_picture(str(source))
                self.assertEqual(symbol, record['symbol'])
                expected = [0 if bit else 255 for row in pixels[y0:y1] for bit in row[x0:x1]]
                with Image.open(panel) as image:
                    self.assertEqual(list(image.convert('L').tobytes()), expected)

    def test_replacement_rejects_installed_dsp_drift_before_any_pedal_operation(self):
        from unittest.mock import patch
        import artwork
        import install_set
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / 'evidence.json'
            evidence.write_text('{}')
            old = root / 'replacement/files'
            old.mkdir(parents=True)
            (old / 'XXTEST.ZD2').write_bytes(b'installed code')
            current = root / 'XXTEST.ZD2'
            current.write_bytes(b'qualified different code')
            current.with_suffix('.ZIC').write_bytes(b'icon')
            argv = ['install_set.py', '--backup', str(root / 'factory'), '--evidence', str(evidence),
                    '--replace-artwork-from', str(old.parent), '--output', str(root / 'output')]
            with patch.object(install_set.sys, 'argv', argv), \
                    patch.object(install_set, 'qualified_artifacts', return_value={'test': current}), \
                    patch.object(install_set, 'verify_backup') as backup, \
                    patch.object(artwork, 'check_variant', side_effect=ValueError('DSP changed')), \
                    patch.object(install_set, 'preflight') as preflight, \
                    patch.object(install_set, 'upstream_operation') as operation:
                with self.assertRaisesRegex(ValueError, 'DSP changed'):
                    install_set.main()
                self.assertEqual(backup.call_count, 2)
                preflight.assert_not_called()
                operation.assert_not_called()

    def test_artwork_preserves_all_non_icon_bytes_and_rejects_other_changes(self):
        import json
        import zlib
        import zoomzt2
        from artwork import ROOT, apply, check_variant, render_frames
        from zd2_from_scratch import build_zd2, ICON_TILE_BYTES
        original = build_zd2(blob=b'original DSP', name='XXTEST', groupname='DELAY',
                             group=7, eid=0x07001300, icon=bytes(ICON_TILE_BYTES))
        cover = ROOT / 'src/msplus/artwork/wavefold.png'
        self.assertEqual([im.size for im in render_frames(cover)], [(72, 97), (102, 128)])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'wavefold'
            (folder / 'build').mkdir(parents=True)
            (folder / 'manifest.json').write_text(json.dumps(dict(filename='XXTEST')))
            artifact = folder / 'build/XXTEST.ZD2'
            artifact.write_bytes(original)
            proof = apply(folder)
            modified = artifact.read_bytes()
            zic = artifact.with_suffix('.ZIC').read_bytes()
            self.assertTrue(proof['dsp_byte_identical'])
            check_variant(original, modified, zic, cover)
            apply(folder)
            self.assertEqual(artifact.read_bytes(), modified, 'Artwork packaging must be idempotent')
            for section in ('DATA', 'INFO', 'ICON'):
                parsed = zoomzt2.ZD2.parse(modified)
                changed = bytearray(parsed[section].data)
                changed[0] ^= 1
                parsed[section].data = bytes(changed)
                damaged = bytearray(zoomzt2.ZD2.build(parsed))
                damaged[8:12] = (zlib.crc32(damaged[12:-16]) ^ 0xffffffff).to_bytes(4, 'little')
                with self.subTest(section=section), self.assertRaises(ValueError):
                    check_variant(original, bytes(damaged), zic, cover)
            with self.assertRaises(ValueError):
                check_variant(original, modified, zic[:-1], cover)


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


class PCMSourceTests(unittest.TestCase):
    def test_derivation_preserves_dependency_and_refuses_source_layout_drift(self):
        from pcm15 import derive
        from upstream import ROOT
        original = (ROOT / 'build/msplus/matujuice/src/custom/scrub/scrub.c').read_text()
        target = 's->buf[s->wp] = (short)(int)v;'
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'source.c', Path(tmp) / 'derived.c'
            source.write_text(original)
            derive(source, output)
            self.assertEqual(source.read_text(), original)
            self.assertIn('mp_pcm15_write(s->buf, s->wp, (int)v);', output.read_text())
            output.unlink()
            for replacement in ('', target + target):
                source.write_text(original.replace(target, replacement))
                with self.assertRaises(RuntimeError):
                    derive(source, output)
                self.assertFalse(output.exists(), 'Refused source must not produce a derived kernel')


class AudioTests(unittest.TestCase):
    def test_linearity_measurement_detects_a_saturated_output_stage(self):
        import json
        import soundfile as sf
        from analyze import validate_linearity
        from reference import linear_output_limit
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wave = np.tile(np.linspace(-1, 1, 100, endpoint=False), 60)
            def recording(name, samples):
                path = root / name
                path.mkdir(exist_ok=True)
                sf.write(path / 'return.wav', np.repeat(samples[:, None], 2, axis=1), 1000, subtype='FLOAT')
                (path / 'report.json').write_text(json.dumps(dict(finite=True, clipped=False, xruns=[])))
            recording('baseline', np.zeros(len(wave)))
            for level in (1, 2, 5, 10, 25, 50, 75, 100):
                recording(f'peak{level:02}', wave*.55*level/100)
            rows, errors = validate_linearity(root)
            self.assertFalse(errors)
            self.assertEqual(len(rows), 8)
            self.assertAlmostEqual(linear_output_limit(root)[0], .55)
            recording('peak100', np.clip(wave*.55, -.3, .3))
            _, errors = validate_linearity(root)
            self.assertEqual(len(errors), 1)
            self.assertIn('level', errors[0])
            self.assertAlmostEqual(linear_output_limit(root)[0], .4125)
            (root / 'peak50/report.json').write_text(json.dumps(dict(finite=False, clipped=False, xruns=[])))
            with self.assertRaisesRegex(ValueError, 'Invalid output-probe recording'):
                linear_output_limit(root)
            recording('peak50', wave*.55*.5)
            recording('peak01', np.zeros(len(wave)))
            _, errors = validate_linearity(root)
            self.assertIn('Quiet diagnostic amplitude is missing', errors[0])

    def test_scorch_linear_reference_detects_faults_and_preserves_high_level_measurements(self):
        import json
        import soundfile as sf
        from unittest.mock import patch
        from native import Kernel
        from reference import compare_scorch
        rate = 44100
        base = np.zeros((rate*6, 2))
        for ch in range(2):
            start = int((.5+ch*2.5)*rate)
            base[start:start+int(1.5*rate), ch] = .002*np.sin(2*np.pi*997*np.arange(int(1.5*rate))/rate)
        # Native blocks require a whole multiple of sixteen frames.
        base = np.pad(base, ((0, (-len(base)) % 16), (0, 0)))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calibration = root / 'calibration.json'
            calibration.write_text(json.dumps(dict(bus_to_return=[1, 1])))
            cases = [['tone', [[2, 100], [3, 100]], 'tone'],
                     ['tone-reference', [[2, 100], [3, 50]], 'tone']]
            (root / 'CASES.json').write_text(json.dumps(cases))
            for label, mix in [('baseline-tone', None), ('tone', 1), ('tone-reference', .5)]:
                folder = root / label
                folder.mkdir()
                audio = base
                if mix is not None:
                    kernel = Kernel('scorch')
                    kernel.coeff[5:7] = [1, mix]
                    audio = np.concatenate([kernel.block(b) for b in base.reshape(-1, 16, 2)])
                    audio = np.clip(audio, -.4, .4)  # independent nonlinear output stage
                sf.write(folder / 'return.wav', audio, rate, subtype='FLOAT')
                (folder / 'report.json').write_text(json.dumps(dict(level_db=-30)))
            with patch('reference.verify_restored_audio'), \
                    patch('reference.linear_output_limit', return_value=(.275, np.ones(2))) as measured_range:
                rows, errors = compare_scorch(root, calibration, root)
                self.assertFalse(errors)
                self.assertEqual(len(rows), 20)
                self.assertTrue(all(r['comparison_domain'] == 'linear' for r in rows if r['capture'] == 'tone-reference'))
                self.assertTrue(all(r['comparison_domain'] != 'linear' for r in rows if r['capture'] == 'tone'))
                measured_range.return_value = (.275, np.full(2, 1.1))
                with self.assertRaisesRegex(ValueError, 'calibration gains differ'):
                    compare_scorch(root, calibration, root)
                measured_range.return_value = (.1, np.ones(2))
                _, errors = compare_scorch(root, calibration, root)
                self.assertTrue(any('exceeds' in e for e in errors))
                measured_range.return_value = (.275, np.ones(2))
                path = root / 'tone-reference/return.wav'
                audio, _ = sf.read(path, always_2d=True)
                sf.write(path, audio*.5, rate, subtype='FLOAT')
                _, errors = compare_scorch(root, calibration, root)
                self.assertTrue(any('reference mismatch' in e for e in errors))

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
