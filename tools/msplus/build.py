#!/usr/bin/env python3
"""Build experimental Plus ports with the pinned upstream builder; no MIDI."""
import argparse
import os
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from upstream import ROOT, STOMPHACKS


def build_container(folder, manifest, env):
    """Keep upstream's legacy numeric floor enabled for lower category groups."""
    # EDTB stores knobs 6–8 in eight bits; the remaining knobs use twelve.
    # A wider UI range can appear to work but truncates current-patch readback.
    for index, param in enumerate(manifest.get('params', []), 1):
        maximum = 255 if 6 <= index <= 8 else 4095
        if not 0 <= param['default'] <= param['max'] <= maximum:
            raise ValueError(f"Knob {index} ({param['name']}) exceeds its EDTB range 0–{maximum}")
    command = [sys.executable, str(STOMPHACKS / 'tools/zd2_make_effect.py')]
    if int(manifest['id'], 16) >> 24 < 7:
        from categories import PLUS_GROUPS, apply
        if int(manifest['id'], 16) >> 24 not in PLUS_GROUPS:
            raise ValueError('Category has not been qualified on the MS-70CDR+')
        staged = dict(manifest, id=f"{0x07000000 | (int(manifest['id'], 16) & 0xffffff):08x}")
        # Keep this beside the real manifest: relative kernels/compiler include
        # paths and the upstream build directory must retain their normal bases.
        with tempfile.NamedTemporaryFile(mode='w', dir=folder, suffix='.json') as temporary:
            json.dump(staged, temporary)
            temporary.flush()
            subprocess.run(command + [temporary.name], check=True, env=env)
        apply(folder)
    else:
        subprocess.run(command + [str(folder / 'manifest.json')], check=True, env=env)


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
            if 'derived_source' in manifest:
                from pcm15 import derive
                derive(dependency / 'src/custom' / effect / (effect + '.c'),
                       (folder / manifest['derived_source']).resolve())
        if 'legacy_manifest' in manifest:
            legacy = (folder / manifest['legacy_manifest']).resolve()
            headers = ROOT / 'build/msplus/headers' / effect
            headers.mkdir(parents=True, exist_ok=True)
            write_param_header(json.loads(legacy.read_text()),
                               headers / (legacy.parent.name + '_params.h'),
                               manifest['legacy_prefix'])
        build_container(folder, manifest, env)
        if (ports / 'artwork' / (effect + '.png')).is_file():
            from artwork import apply
            apply(folder)


if __name__ == '__main__':
    main()
