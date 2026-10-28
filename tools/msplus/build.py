#!/usr/bin/env python3
"""Build experimental Plus ports with the pinned upstream builder; no MIDI."""
import argparse
import os
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
    for effect in args.effects or available:
        subprocess.run([sys.executable, str(STOMPHACKS / 'tools/zd2_make_effect.py'),
                        str(ports / effect / 'manifest.json')], check=True, env=env)


if __name__ == '__main__':
    main()
