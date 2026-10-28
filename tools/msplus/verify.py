#!/usr/bin/env python3
"""Final read-only audit: stock patch, unchanged bank/list, no custom files."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path

from upstream import ROOT
from audition import TempPatch, verify_backup
from file_session import FileSession, MidoTransport
from pedal_common import editor_off


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('backup', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
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
            if flst != original:
                raise RuntimeError('Effect list differs from the initial backup; inspect before continuing')
            absent = []
            for path in sorted((ROOT / 'src/msplus').glob('*/manifest.json')):
                manifest = json.loads(path.read_text())
                for suffix in ('.ZD2', '.ZIC'):
                    name = manifest['filename'] + suffix
                    if sess.file_check(name):
                        raise RuntimeError('Experimental file remains installed: ' + name)
                    sess.close()
                    absent.append(name)
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
                      effect_list_byte_identical=True, flst_sha256=hashlib.sha256(flst).hexdigest(),
                      absent_custom_files=absent, maximum_bytes=maximum, available_bytes=available)
        (args.output / 'VERIFIED.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
