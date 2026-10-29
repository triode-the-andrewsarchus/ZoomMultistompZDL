#!/usr/bin/env python3
"""Read-only audit: stock scratch/bank, factory catalogue and expected DIY files."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
from pathlib import Path

from upstream import ROOT
from audition import TempPatch, verify_backup
from file_session import FileSession, MidoTransport
from pedal_common import editor_off
from flst_check import validate_flst


def check_catalogue(original, actual, manifests):
    entries = []
    for data in (original, actual):
        ok, problems, parsed = validate_flst(data)
        if not ok:
            raise RuntimeError(f'Invalid effect catalogue: {problems}')
        entries.append(Counter(parsed))
    expected = Counter((int(m['id'], 16) >> 24, m['filename'] + '.ZD2',
                        m['version'], int(m['id'], 16), 1) for m in manifests)
    if len(actual) != len(original) or entries[1] != entries[0] + expected:
        raise RuntimeError('Effect catalogue differs from factory entries plus exactly the requested ports')
    if not manifests and actual != original:
        raise RuntimeError('Empty custom catalogue is not byte-identical to the backup')


def check_files(session, paths, installed):
    absent, verified = [], {}
    for path in paths:
        manifest = json.loads(path.read_text())
        for suffix in ('.ZD2', '.ZIC'):
            name = manifest['filename'] + suffix
            if path.parent.name in installed:
                expected = (path.parent / 'build' / name).read_bytes()
                data = session.download(name)
                session.close()
                if data != expected:
                    raise RuntimeError('Installed file differs from its build: ' + name)
                verified[name] = hashlib.sha256(data).hexdigest()
            else:
                if session.file_check(name):
                    raise RuntimeError('Unexpected experimental file remains installed: ' + name)
                session.close()
                absent.append(name)
    return absent, verified


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('backup', type=Path)
    ap.add_argument('output', type=Path)
    ap.add_argument('--installed', nargs='+', default=[], help='Exact musical ports expected to remain installed')
    args = ap.parse_args()
    paths = sorted((ROOT / 'src/msplus').glob('*/manifest.json'))
    available = {p.parent.name for p in paths} - {'gain', 'calibrate', 'meminfo', 'linearity'}
    if len(set(args.installed)) != len(args.installed) or set(args.installed) - available:
        ap.error('--installed requires distinct musical port names')
    manifests = [json.loads(p.read_text()) for p in paths if p.parent.name in args.installed]
    verify_backup(args.backup)
    args.output.mkdir(parents=True, exist_ok=False)
    with open('/tmp/ZoomMultistompZDL-midi.lock', 'w') as lock, (args.output / 'wire.log').open('w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        patch = TempPatch(log, args.backup)
        patch.verify_saved()
        patch.drain()
        sess = FileSession(MidoTransport(patch.pedal.inport, patch.pedal.outport))
        try:
            sess.pcmode_on()
            flst = sess.download('FLST_SEQ.ZT2')
            sess.close()
            original = (args.backup / 'files/FLST_SEQ.ZT2').read_bytes()
            check_catalogue(original, flst, manifests)
            absent, verified = check_files(sess, paths, set(args.installed))
            maximum, available = sess.disk_usage()
            sess.close()
            sess.pcmode_off()
        except BaseException:
            if not sess.abort():
                print('DO NOT POWER-CYCLE: file-session close not acknowledged', flush=True)
            raise
        finally:
            editor_off(patch.pedal)
            patch.pedal.disconnect()
        report = dict(autosave_off_confirmed=True, stock_only_temp_patch=True,
                      saved_patch_count=100, saved_patch_defined_bytes_unchanged=True,
                      factory_catalogue_entries_unchanged=True, effect_list_byte_identical=flst == original,
                      installed_ports=args.installed, verified_installed_files=verified,
                      flst_sha256=hashlib.sha256(flst).hexdigest(),
                      absent_custom_files=absent, maximum_bytes=maximum, available_bytes=available)
        (args.output / 'VERIFIED.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
