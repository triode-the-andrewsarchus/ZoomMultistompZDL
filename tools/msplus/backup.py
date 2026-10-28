#!/usr/bin/env python3
"""CRC-checked full backup using Stomphacks' enumeration gate and file engine.

Never uploads files or patches. A fresh destination is required. VERIFIED.json
is written only after all files, all patch memories and the final effect list
have verified. Leave the pedal powered if any file-session cleanup fails.
"""
import argparse
import binascii
import hashlib
import json
import time
from pathlib import Path

import upstream  # noqa: F401
import backup_pedal
import zoomzt2
from decode_preset import ZPTC
from file_session import FileSession, MidoTransport, tail_to_int
from stock_catalog import STOCK_IDS


class CheckedInput:
    """Bound upstream's blocking reads and reject corrupt patch replies."""
    def __init__(self, port):
        self.port = port

    def receive(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            msg = self.port.poll()
            if msg is None:
                time.sleep(0.002)
                continue
            if msg.type != 'sysex':
                raise RuntimeError(f'Unexpected MIDI response: {msg}')
            data = bytes(msg.data)
            offsets = {b'\x64\x12': 6, b'\x45\x00': 10}
            offset = offsets.get(data[3:5])
            if offset is not None:
                length = data[offset] + 128 * data[offset + 1]
                body = zoomzt2.zoomzt2().unpack(data[offset + 2:-5])
                if len(body) != length or binascii.crc32(body) != (tail_to_int(data[-5:]) ^ 0xffffffff):
                    raise RuntimeError('Patch CRC/length mismatch; backup refused')
            return msg
        raise TimeoutError('No reply within 5 seconds; stopping')

    def __getattr__(self, name):
        return getattr(self.port, name)


def stock_patch(data):
    patch = ZPTC.parse(data)
    if patch.length > len(data) or patch.target != 0x40000:
        raise ValueError('Unexpected patch size/target')
    ids = set(patch.ids)
    ids.update(e.reversed.bitwise.id for e in patch.EDTB.effects)
    unknown = ids - STOCK_IDS - {0}
    if unknown:
        raise ValueError(f'Non-stock patch IDs: {[hex(i) for i in unknown]}')
    return patch


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('destination', type=Path)
    args = ap.parse_args()
    args.destination.mkdir(parents=True, exist_ok=False)
    files = args.destination / 'files'
    files.mkdir()
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        raise SystemExit('Pedal not found')
    pedal.inport = CheckedInput(pedal.inport)
    sess = FileSession(MidoTransport(pedal.inport, pedal.outport))
    try:
        sess.pcmode_on()
        flst = sess.download('FLST_SEQ.ZT2')
        sess.close()
        (files / 'FLST_SEQ.ZT2').write_bytes(flst)
        names = backup_pedal.enumerate_files(pedal, args.destination, files)
        if len(names) != len(set(names)) or any(Path(n).name != n for n in names):
            raise ValueError('Invalid or duplicate directory names')
        for i, name in enumerate(names, 1):
            data = sess.download(name)
            sess.close()
            if not data:
                raise RuntimeError(f'Empty file: {name}')
            (files / name).write_bytes(data)
            print(f'[{i}/{len(names)}] {name}: {len(data)} CRC-checked bytes', flush=True)
        count, size, bank = pedal.patch_check()
        if not (1 <= count <= 200 and size > 0 and bank > 0):
            raise ValueError('Unexpected patch inventory')
        for loc in range(1, count + 1):
            data = pedal.patch_download(loc)
            stock_patch(data)
            (args.destination / f'PATCH_{loc:03d}.ZPTC').write_bytes(data)
            print(f'Patch {loc}/{count}: CRC checked, stock-only', flush=True)
        if sess.download('FLST_SEQ.ZT2') != flst:
            raise RuntimeError('Effect list changed during backup')
        sess.close()
        manifest = {str(p.relative_to(args.destination)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(args.destination.rglob('*')) if p.is_file()}
        (args.destination / 'VERIFIED.json').write_text(json.dumps({
            'files': len(names), 'patches': count, 'sha256': manifest,
            'stock_only_patches': True,
        }, indent=2) + '\n')
        print('Backup VERIFIED', flush=True)
    except BaseException:
        if not sess.abort():
            print('DO NOT POWER-CYCLE: file-session cleanup not verified', flush=True)
        raise
    finally:
        sess.pcmode_off()
        pedal.disconnect()


if __name__ == '__main__':
    main()
