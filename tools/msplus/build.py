#!/usr/bin/env python3
"""Build experimental Plus ports with the pinned upstream builder; no MIDI."""
import argparse
import os
import json
import subprocess
import sys
from pathlib import Path

from upstream import ROOT, STOMPHACKS


def main():
    ports = ROOT / 'src/msplus'
    available = sorted(path.parent.name for path in ports.glob('*/manifest.json'))
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('effects', nargs='*', help='Port names; default: all available ports')
    args = ap.parse_args()
    unknown = set(args.effects) - set(available)
    if unknown:
        ap.error(f'Unknown ports {sorted(unknown)}; available: {available}')
    env = os.environ.copy()
    env.setdefault('ZOOM_TI_CGT', str(ROOT / 'build/msplus/ti/ti-cgt-c6000_8.3.15'))
    if not (Path(env['ZOOM_TI_CGT']) / 'bin/cl6x').is_file():
        ap.error('Install TI C6000 tools and set ZOOM_TI_CGT to their root')
    sys.path.insert(0, str(ROOT / 'build'))
    sys.path.insert(0, str(ROOT / 'src/airwindows/common'))
    from manifest_params import write_param_header
    for effect in args.effects or available:
        folder = ports / effect
        manifest = json.loads((folder / 'manifest.json').read_text())
        if manifest.get('dependency') == 'matujuice-v1.5':
            dependency = ROOT / 'build/msplus/matujuice'
            pin = json.loads((ROOT / 'tools/msplus/upstream.lock.json').read_text())['matujuice-v1.5']
            actual = subprocess.check_output(['git', '-C', str(dependency), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != pin:
                raise RuntimeError('Matujuice dependency differs from pinned v1.5 source')
            subprocess.run(['git', '-C', str(dependency), 'diff', '--exit-code', 'HEAD', '--', 'src'], check=True)
        if 'legacy_manifest' in manifest:
            legacy = (folder / manifest['legacy_manifest']).resolve()
            headers = ROOT / 'build/msplus/headers' / effect
            headers.mkdir(parents=True, exist_ok=True)
            write_param_header(json.loads(legacy.read_text()),
                               headers / (legacy.parent.name + '_params.h'),
                               manifest['legacy_prefix'])
        subprocess.run([sys.executable, str(STOMPHACKS / 'tools/zd2_make_effect.py'),
                        str(ports / effect / 'manifest.json')], check=True, env=env)


if __name__ == '__main__':
    main()
