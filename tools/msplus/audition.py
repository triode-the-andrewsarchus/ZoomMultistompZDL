#!/usr/bin/env python3
"""Audition ONE installed effect in a one-slot UNSAVED patch, then restore it.

No patch-upload/save, file-upload/delete, reset or firmware commands exist here.
Requires a verified full backup; rechecks every saved patch after audition.
Installation/removal remain separate upstream pedal_diy operations.
"""
import argparse
import fcntl
import hashlib
import json
import time
from pathlib import Path

import upstream  # noqa: F401
import mido
import zoomzt2
from audio import AudioRig, run_capture, temporary_quantum
from upstream import ROOT
from native import MATU_PORTS
from backup import CheckedInput, stock_patch
from pedal_diy import check_envelope, check_zic
from decode_preset import ZPTC
from file_session import FileSession, MidoTransport
from pedal_common import assert_autosave_off, editor_off


# Reviewed temporary parameter edits: bypass=0, identity=1, knobs start at 2.
CASES = {
    'XXZGENLS': [(name, [(2, 0), (3, 100), (4, 0), (5, mix)], 'sweep')
                 for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
                + [('wobble', [(2, 100)], 'sweep')],
    'XXZMEM': [('disarmed', [(2, 0)], 'silence'), ('armed', [(2, 1)], 'silence')],
    'XXZCAL': [('peak50', [(2, 50)], 'silence'), ('peak10', [(2, 10)], 'silence'),
               ('volume10', [(2, 50), (0, 10, 0x64)], 'silence')],
    'XXZGAIN': [(name, [(2, level), (0, enabled)], 'sweep')
                for name, level, enabled in [('unity', 100, 1), ('half', 50, 1),
                                            ('quarter', 25, 1), ('zero', 0, 1), ('bypass', 50, 0)]]
               + [('tone', [(0, 1), (2, 100)], 'tone')],
    'XXZFLWR': [(name, [(2, 30), (3, mix)], 'sweep') for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
               + [('extreme', [(2, 100)], 'sweep')],
    'XXZKLNG': [(name, [(2, 20), (3, 0), (4, mix)], 'tone')
                for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
               + [('extreme', [(2, 100), (3, 100)], 'sweep')],
    'XXZSCRCH': [(name, [(3, mix)], 'sweep') for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
                + [('tone', [(2, 100)], 'tone')],
    'XXZCRRPT': [(name, [(5, mix)], 'sweep') for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
                + [('tone', [(2, 100), (3, 100), (4, 100), (6, 10)], 'tone')],
    'XXZDUST': [('distortion', [(2, 0)], 'sweep'), ('octave', [(2, 100)], 'tone'),
                ('motor', [(2, 0), (3, 100)], 'tone'), ('zero', [(5, 0)], 'sweep')],
    'XXZHOWL': [(name, [(2, 35), (3, 50), (4, mix)], 'sweep') for name, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
               + [('extreme', [(2, 100), (3, 100)], 'sweep')],
}


BUFFERED_PORTS = {'microloom', 'shatter', 'arrakis', 'taffy', 'dissolve', 'mangle',
                  'rooms', 'hydra', 'spiral', 'stasis', 'rewire', 'gyre', 'galactic', 'spool', 'oxide'}


MATU_CASES = {
    'wavefold': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100}, 'tone'),
                 ('drive', {'Drive': 100}, 'tone'), ('symmetry', {'Symm': 95, 'Tone': 100}, 'tone')],
    'dualshft': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100}, 'tone'),
                 ('pitch', {'Ptch1': 66, 'Ptch2': 0}, 'tone')],
    'formant': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100}, 'tone'),
                ('choir', {'Choir': 16, 'Size': 5}, 'tone')],
    'eugate': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100}, 'sustain'),
               ('pattern', {'Notes': 3, 'Steps': 7}, 'sustain')],
    'dubsiren': [('siren', {'Vol': 25}, 'silence'), ('prime', {}, 'sustain'),
                 ('tail', {'enabled': 0}, 'silence')],
    'sgnl': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100, 'Codec': 0, 'Loss': 0}, 'sweep'),
             ('damage', {'Loss': 70, 'Codec': 40}, 'tone')],
    'scrub': [('dry', {'Mix': 0}, 'sweep'), ('prime', {}, 'sustain'),
              ('wet', {'Mix': 100, 'Pos': 500}, 'silence'),
              ('scan', {'Pos': 400}, 'silence')],
    'griddly': [('dry', {'Mix': 0}, 'sweep'), ('wet', {'Mix': 100, 'Time': 80}, 'sweep'),
                ('prime', {}, 'sustain'), ('tail', {'enabled': 0}, 'silence')],
    'synceq': [('default', {}, 'sweep'), ('low', {'Low': 24}, 'sweep'),
               ('cut', {'HiCut': 10}, 'sweep')],
    'breather': [('dry', {'Depth': 0, 'Verb': 0}, 'sweep'),
                 ('pump', {'Depth': 80, 'Verb': 35}, 'sustain'),
                 ('reverb', {'Depth': 0, 'Verb': 100}, 'sweep')],
    'dirtbox': [('dry', {'Mix': 0, 'Level': 20}, 'sweep')]
                + [(f'model{i}', {'Mix': 100, 'Model': i}, 'tone') for i in range(7)],
    'sweep': [('dry', {'Mix': 0}, 'sweep')]
              + [(f'engine{i}', {'Mix': 100, 'Type': i}, 'sweep') for i in range(8)],
}


def reviewed_cases(manifest):
    if manifest['filename'] in CASES:
        return CASES[manifest['filename']]
    name = manifest['kernel'].removesuffix('.c')
    if name in MATU_PORTS:
        knobs = {p['name']: i+2 for i, p in enumerate(manifest['params'])}
        knobs['enabled'] = 0
        return [(label, [(knobs[key], value) for key, value in edits.items()], kind)
                for label, edits, kind in MATU_CASES[name]]
    if name not in BUFFERED_PORTS:
        raise ValueError('No reviewed test cases for this effect')
    knobs = {p['name']: i+2 for i, p in enumerate(manifest['params'])}
    cases = [(label, [(knobs['Mix'], mix)], 'sweep')
             for label, mix in [('dry', 0), ('half', 50), ('wet', 100)]]
    if name == 'rooms':
        cases.extend((f'mode{value}', [(knobs['Mode'], value)], 'sweep')
                     for value in [20, 40, 60, 80, 100])
    elif name == 'stasis':
        cases = [('dry', [(knobs['Capture'], 1), (knobs['Mix'], 0)], 'sweep'),
                 ('prime', [(knobs['Length'], 100), (knobs['Mix'], 100)], 'sustain'),
                 ('hold', [(knobs['Capture'], 2)], 'silence'),
                 ('hold-off', [(0, 0)], 'silence'),
                 ('release', [(knobs['Capture'], 1)], 'sweep')]
    return cases


def verify_backup(folder):
    manifest = json.loads((folder / 'VERIFIED.json').read_text())
    if manifest['patches'] != 100 or not manifest['stock_only_patches']:
        raise ValueError('Expected a complete stock-only MS-70CDR+ backup')
    if len(list((folder / 'files').iterdir())) != manifest['files'] or len(list(folder.glob('PATCH_*.ZPTC'))) != 100:
        raise ValueError('Backup inventory does not match its verification marker')
    for name, digest in manifest['sha256'].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Backup hash mismatch: {name}')
    for path in (folder / 'files').iterdir():
        checker = {'.ZD2': check_envelope, '.ZIC': check_zic}.get(path.suffix.upper())
        if checker and checker(path.read_bytes()):
            raise ValueError(f'Invalid backup container: {path.name}')
    return manifest


def defined_patch(data):
    patch = ZPTC.parse(data)
    if not 0 < patch.length <= len(data):
        raise ValueError('Invalid PTCF length')
    return data[:patch.length]


class TempPatch:
    def __init__(self, log, backup):
        ports = [p for p in mido.get_input_names() if p.startswith('ZOOM MS Plus Series')]
        if len(ports) != 1:
            raise RuntimeError('Expected exactly one MS Plus MIDI input')
        self.pedal = zoomzt2.zoomzt2()
        if not self.pedal.connect():
            raise RuntimeError('Pedal not found')
        self.pedal.inport = CheckedInput(self.pedal.inport)
        self.log = log
        self.backup = backup
        self.modified = False
        self.protocol_ok = True
        transport = MidoTransport(self.pedal.inport, self.pedal.outport)
        transport.send([0x7e, 0x7f, 0x06, 0x01])
        identity = transport.recv(3)
        if identity is None or identity[:9] != bytes.fromhex('7e000602526e002600') or identity[9:] != b'1.10':
            raise RuntimeError('Expected the verified MS-70CDR+ firmware 1.10 identity')
        self.log.write('IDENTITY ' + identity.hex() + '\n')
        assert_autosave_off(self.pedal)
        self.original = self.current()
        stock_patch(self.original)
        if ZPTC.parse(self.original).fx_count != 1:
            raise ValueError('Audition requires a one-slot scratch patch; no automatic patch clearing')
        self.restore_parameter_count = self.original_parameter_count()

    def transmit_sysex(self, data):
        if not (data == [0x52, 0, 0x6e, 0x64, 0x13]
                or (len(data) == 13 and data[:6] == [0x52, 0, 0x6e, 0x64, 0x20, 0]
                    and ((data[6] == 0 and 0 <= data[7] <= 11)
                         or (data[6:8] == [0x64, 0] and data[8] <= 100 and data[9:] == [0, 0, 0, 0])))):
            raise ValueError('Only current-patch reads, slot-zero edits and bounded patch volume are allowed')
        self.log.write('TX ' + bytes(data).hex() + '\n')
        self.log.flush()
        self.pedal.outport.send(mido.Message('sysex', data=data))

    def drain(self):
        # The pedal emits unsolicited current-patch notifications on effect
        # changes. Consume only known notifications before a fresh request.
        while True:
            msg = self.pedal.inport.poll()
            if msg is None:
                return
            data = bytes(msg.data)
            self.log.write('RX pending ' + data.hex() + '\n')
            if not (data[3:5] in (b'\x64\x12', b'\x00\x00')
                    or data[3:6] in (b'\x64\x20\x01', b'\x64\x20\x00')):
                raise RuntimeError(f'Unexpected pending reply: {data.hex()}')

    def current(self):
        self.drain()
        self.transmit_sysex([0x52, 0, 0x6e, 0x64, 0x13])
        for _ in range(30):
            msg = self.pedal.inport.receive()
            data = bytes(msg.data)
            self.log.write('RX ' + data.hex() + '\n')
            self.log.flush()
            if data[3:5] == b'\x64\x12':
                # CheckedInput already verified the CRC and length.
                patch = bytes(self.pedal.unpack(data[8:-5]))
                ZPTC.parse(patch)
                return patch
            if data[3:6] not in (b'\x64\x20\x01', b'\x64\x20\x00'):
                raise RuntimeError(f'Unexpected reply: {data.hex()}')
        raise RuntimeError('No current-patch reply')

    def edit(self, parameter, value, slot=0):
        # Fixed slot zero. Only effect ID, on/off and ten documented knobs.
        if not ((slot == 0 and 0 <= parameter <= 11 and 0 <= value < (1 << 29))
                or (slot == 0x64 and parameter == 0 and 0 <= value <= 100)):
            raise ValueError('Invalid temporary parameter edit')
        self.modified = True
        try:
            self._edit_checked(parameter, value, slot)
        except BaseException:
            self.protocol_ok = False
            raise

    def _edit_checked(self, parameter, value, slot):
        self.transmit_sysex([0x52, 0, 0x6e, 0x64, 0x20, 0, slot, parameter]
                  + [(value >> shift) & 127 for shift in range(0, 35, 7)])
        time.sleep(0.12)
        patch = ZPTC.parse(self.current())
        effect = patch.EDTB.effects[0].reversed.bitwise
        actual = (patch.PPRM.reversed.bitwise.patchVolume if slot == 0x64 else
                  int(effect.enabled) if parameter == 0 else
                  effect.id if parameter == 1 else effect[f'param{parameter - 1}'])
        if actual != value or (parameter == 1 and patch.ids[0] != value):
            raise RuntimeError(f'Temp edit readback mismatch: parameter {parameter}, wanted {value}, got {actual}')

    def original_parameter_count(self):
        effect = stock_patch(self.original).EDTB.effects[0].reversed.bitwise
        matching = [p for p in (self.backup / 'files').glob('*.ZD2')
                    if int.from_bytes(p.read_bytes()[96:100], 'little') == effect.id]
        if len(matching) != 1:
            raise RuntimeError('Cannot identify original stock effect for restoration')
        config = zoomzt2.ZD2.parse(matching[0].read_bytes())
        parameters = json.loads(config['PRME']['xml'])['Parameters']
        if not 1 <= len(parameters) <= 10:
            raise RuntimeError('Unexpected original stock parameter count')
        return len(parameters)

    def restore(self):
        original = stock_patch(self.original)
        effect = original.EDTB.effects[0].reversed.bitwise
        self.edit(1, effect.id)
        for index in range(self.restore_parameter_count):
            self.edit(index + 2, effect[f'param{index + 1}'])
        self.edit(0, int(effect.enabled))
        if ZPTC.parse(self.current()).PPRM.reversed.bitwise.patchVolume != original.PPRM.reversed.bitwise.patchVolume:
            self.edit(0, original.PPRM.reversed.bitwise.patchVolume, slot=0x64)
        final = stock_patch(self.current())
        if final.ids != original.ids or final.EDTB != original.EDTB or final.PPRM != original.PPRM:
            raise RuntimeError('Restored patch differs from original effect settings')
        editor_off(self.pedal)

    def verify_saved(self):
        self.drain()
        count, _, _ = self.pedal.patch_check()
        if count != 100:
            raise RuntimeError('Patch count changed')
        for loc in range(1, count + 1):
            data = bytes(self.pedal.patch_download(loc))
            old = (self.backup / f'PATCH_{loc:03d}.ZPTC').read_bytes()
            if defined_patch(data) != defined_patch(old):
                raise RuntimeError(f'Saved patch {loc} changed: stopping')
        print('All 100 saved patches: defined PTCF bytes identical to backup', flush=True)

    def verify_installed(self, artifact):
        self.drain()
        sess = FileSession(MidoTransport(self.pedal.inport, self.pedal.outport))
        try:
            sess.pcmode_on()
            data = sess.download(artifact.name)
            sess.close()
            if data != artifact.read_bytes():
                raise RuntimeError('Installed binary is not byte-identical to local artifact')
            sess.pcmode_off()
        except BaseException:
            if not sess.abort():
                print('DO NOT POWER-CYCLE: failed to verify file session cleanup', flush=True)
            raise
        print('Independent effect readback byte-identical', flush=True)



def capture_trial(directory, kind, level, rig):
    sends = [f'AF16Rig Audio Pro:playback_AUX{i}' for i in (6, 7)]
    returns = [f'AF16Rig Audio Pro:capture_AUX{i}' for i in (2, 3)]
    return run_capture(directory, sends, returns, kind, level, rig=rig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('effect', type=Path)
    ap.add_argument('backup', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    verify_backup(args.backup)
    manifest = json.loads((args.effect / 'manifest.json').read_text())
    cases = reviewed_cases(manifest)
    args.output.mkdir(parents=True, exist_ok=False)
    with temporary_quantum(1024), AudioRig(
            [f'AF16Rig Audio Pro:playback_AUX{i}' for i in (6, 7)],
            [f'AF16Rig Audio Pro:capture_AUX{i}' for i in (2, 3)]) as rig, open('/tmp/ZoomMultistompZDL-midi.lock', 'w') as lock, open(args.output / 'wire.log', 'w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session = TempPatch(log, args.backup)
        (args.output / 'ORIGINAL.ZPTC').write_bytes(session.original)
        sources = [args.effect / 'manifest.json', *args.effect.glob('*.c'), *sorted((ROOT / 'src/msplus/common').glob('*.h'))]
        original_source = ROOT / 'src/custom' / args.effect.name / (args.effect.name + '.c')
        if original_source.exists():
            sources.append(original_source)
        if 'legacy_manifest' in manifest:
            legacy = (args.effect / manifest['legacy_manifest']).resolve()
            sources.extend([legacy, legacy.parent / (legacy.parent.name + '.c')])
            if manifest.get('dependency') == 'matujuice-v1.5':
                sources.append(ROOT / 'build/msplus/matujuice/src/custom/common/drytag.h')
            else:
                sources.extend([ROOT / 'src/airwindows/common/zoom_params.h',
                                ROOT / 'src/airwindows/common/tape_controls.h'])
        (args.output / 'SOURCES.json').write_text(json.dumps({str(p.resolve().relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, indent=2) + '\n')
        try:
            session.verify_saved()
            artifact = args.effect / 'build' / (manifest['filename'] + '.ZD2')
            (args.output / 'BUILT.ZD2').write_bytes(artifact.read_bytes())
            session.verify_installed(artifact)
            session.edit(0, 0)
            reports = {'baseline': capture_trial(args.output / 'baseline', 'sweep', -30, rig),
                       'baseline-tone': capture_trial(args.output / 'baseline-tone', 'tone', -30, rig)}
            session.edit(1, int(manifest['id'], 16))
            session.edit(0, 1)
            for label, edits, kind in cases:
                for edit in edits:
                    session.edit(*edit)
                time.sleep(0.15)
                level = -30
                if manifest['filename'] == 'XXZCRRPT' and label == 'tone':
                    level = -20
                reports[label] = capture_trial(args.output / label, kind, level, rig)
                print(label, {k: reports[label][k] for k in ('silent', 'clipped', 'xruns')}, flush=True)
            session.edit(0, 1)
            reports['silence'] = capture_trial(args.output / 'silence', 'silence', -30, rig)
            (args.output / 'captures.json').write_text(json.dumps(reports, indent=2) + '\n')
        finally:
            if not session.protocol_ok:
                raise RuntimeError('Unexpected MIDI response: stopped. Temp patch may still contain the experiment; keep pedal powered and inspect wire.log before cleanup.')
            if session.modified:
                session.restore()
            else:
                editor_off(session.pedal)
                time.sleep(0.1)
            session.verify_saved()
            session.pedal.disconnect()
            (args.output / 'RESTORED').write_text('Original temp effect settings restored; all defined saved-patch bytes unchanged.\n')
            print('Original temporary patch restored', flush=True)


if __name__ == '__main__':
    main()
