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
import jack
import mido
import numpy as np
import soundfile as sf
import zoomzt2
from audio import analyze, capture, stimulus
from backup import CheckedInput, stock_patch
from decode_preset import ZPTC
from file_session import FileSession, MidoTransport
from pedal_common import assert_autosave_off, editor_off


def verify_backup(folder):
    manifest = json.loads((folder / 'VERIFIED.json').read_text())
    if manifest['patches'] != 100 or not manifest['stock_only_patches']:
        raise ValueError('Expected a complete stock-only MS-70CDR+ backup')
    if len(list((folder / 'files').iterdir())) != manifest['files'] or len(list(folder.glob('PATCH_*.ZPTC'))) != 100:
        raise ValueError('Backup inventory does not match its verification marker')
    for name, digest in manifest['sha256'].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Backup hash mismatch: {name}')
    return manifest


def defined_patch(data):
    patch = ZPTC.parse(data)
    if not 0 < patch.length <= len(data):
        raise ValueError('Invalid PTCF length')
    return data[:patch.length]


class TempPatch:
    def __init__(self, log, backup):
        self.pedal = zoomzt2.zoomzt2()
        if not self.pedal.connect():
            raise RuntimeError('Pedal not found')
        self.pedal.inport = CheckedInput(self.pedal.inport)
        self.log = log
        self.backup = backup
        self.modified = False
        self.protocol_ok = True
        assert_autosave_off(self.pedal)
        self.original = self.current()
        stock_patch(self.original)
        if ZPTC.parse(self.original).fx_count != 1:
            raise ValueError('Audition requires a one-slot scratch patch; no automatic patch clearing')

    def send(self, data):
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
        self.send([0x52, 0, 0x6e, 0x64, 0x13])
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

    def edit(self, parameter, value):
        # Fixed slot zero. Only effect ID, on/off and ten documented knobs.
        if not (0 <= parameter <= 11 and 0 <= value < (1 << 29)):
            raise ValueError('Invalid temporary parameter edit')
        self.modified = True
        try:
            self._edit_checked(parameter, value)
        except BaseException:
            self.protocol_ok = False
            raise

    def _edit_checked(self, parameter, value):
        self.send([0x52, 0, 0x6e, 0x64, 0x20, 0, 0, parameter]
                  + [(value >> shift) & 127 for shift in range(0, 35, 7)])
        time.sleep(0.12)
        patch = ZPTC.parse(self.current())
        effect = patch.EDTB.effects[0].reversed.bitwise
        actual = (int(effect.enabled) if parameter == 0 else
                  effect.id if parameter == 1 else effect[f'param{parameter - 1}'])
        if actual != value or (parameter == 1 and patch.ids[0] != value):
            raise RuntimeError(f'Temp edit readback mismatch: parameter {parameter}, wanted {value}, got {actual}')

    def restore(self):
        original = stock_patch(self.original)
        effect = original.EDTB.effects[0].reversed.bitwise
        self.edit(1, effect.id)
        # Only restore parameters actually declared by the stock effect. Setting
        # undeclared knobs is outside the known-safe command vocabulary.
        matching = [p for p in (self.backup / 'files').glob('*.ZD2')
                    if int.from_bytes(p.read_bytes()[96:100], 'little') == effect.id]
        if len(matching) != 1:
            raise RuntimeError('Cannot identify original stock effect for restoration')
        config = zoomzt2.ZD2.parse(matching[0].read_bytes())
        parameters = json.loads(config['PRME']['xml'])['Parameters']
        if not 1 <= len(parameters) <= 10:
            raise RuntimeError('Unexpected original stock parameter count')
        for index in range(len(parameters)):
            self.edit(index + 2, effect[f'param{index + 1}'])
        self.edit(0, int(effect.enabled))
        final = stock_patch(self.current())
        if final.ids != original.ids or final.EDTB != original.EDTB:
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



def record(directory, kind, level):
    directory.mkdir()
    client = jack.Client('zdl-hil', no_start_server=True)
    try:
        rate = client.samplerate
        test = stimulus(rate, level, kind)
        sends = [f'AF16Rig Audio Pro:playback_AUX{i}' for i in (6, 7)]
        returns = [f'AF16Rig Audio Pro:capture_AUX{i}' for i in (2, 3)]
        recording, xruns = capture(client, test, sends, returns)
    finally:
        client.close()
    sf.write(directory / 'send.wav', test, rate, subtype='FLOAT')
    sf.write(directory / 'return.wav', recording, rate, subtype='FLOAT')
    report = analyze(test, recording, rate)
    report.update(rate=rate, sends=sends, returns=returns, xruns=xruns, kind=kind, level_db=level)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if xruns or not report['finite'] or report['clipped']:
        raise RuntimeError('Invalid audio capture; stopping audition')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('effect', type=Path)
    ap.add_argument('backup', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    verify_backup(args.backup)
    manifest = json.loads((args.effect / 'manifest.json').read_text())
    args.output.mkdir(parents=True, exist_ok=False)
    with open('/tmp/ZoomMultistompZDL-midi.lock', 'w') as lock, open(args.output / 'wire.log', 'w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session = TempPatch(log, args.backup)
        (args.output / 'ORIGINAL.ZPTC').write_bytes(session.original)
        try:
            session.verify_saved()
            session.verify_installed(args.effect / 'build' / (manifest['filename'] + '.ZD2'))
            session.edit(0, 0)
            reports = {'baseline': record(args.output / 'baseline', 'sweep', -30)}
            session.edit(1, int(manifest['id'], 16))
            session.edit(0, 1)
            if manifest['filename'] == 'XXZGAIN':
                cases = [('unity', 100, 1), ('half', 50, 1), ('quarter', 25, 1),
                         ('zero', 0, 1), ('bypass', 50, 0)]
                for label, level, enabled in cases:
                    session.edit(2, level)
                    session.edit(0, enabled)
                    time.sleep(0.15)
                    reports[label] = record(args.output / label, 'sweep', -30)
                    print(label, {k: reports[label][k] for k in ('silent', 'clipped', 'xruns')}, flush=True)
            elif manifest['filename'] == 'XXZFLWR':
                for label, mix in [('dry', 0), ('half', 50), ('wet', 100)]:
                    session.edit(3, mix)
                    reports[label] = record(args.output / label, 'sweep', -30)
                    print(label, {k: reports[label][k] for k in ('silent', 'clipped', 'xruns')}, flush=True)
            else:
                raise ValueError('No reviewed test cases for this effect')
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
