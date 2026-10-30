#!/usr/bin/env python3
"""Keep the complete hardware-qualified musical set installed for manual audition.

Uses the upstream installer unchanged. Never selects an experiment or saves a
patch. Missing/failed/stale evidence stops before any pedal operation. A transfer
failure stops immediately; there is no rollback or retry of uncertain writes.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from upstream import ROOT
from run import preflight, upstream_operation
from audition import verify_backup
from audio import require_loopback, verify_restored_audio
from analyze import EFFECT_CHECKS


def check_measurements(name, evidence):
    analysis = json.loads(evidence.read_text())
    if analysis['passed'] is not True or analysis['errors']:
        raise RuntimeError(f'{name}: hardware evidence has failed checks')
    checks = {'capture_integrity', 'signal_above_noise', 'zero_input_stability'}
    if name in EFFECT_CHECKS:
        checks.add(EFFECT_CHECKS[name][1])
    if name == 'scorch':
        checks.add('native_DSP_harmonics')
    if (evidence.parent / 'dry').is_dir():
        checks.add('dry_path_gain')
    if not checks <= set(analysis['checks']):
        raise RuntimeError(f'{name}: hardware analysis does not cover required checks')
    verify_restored_audio(evidence.parent, ROOT)
    require_loopback(json.loads((evidence.parent / 'baseline/report.json').read_text()))


def check_sources(folder, manifest, evidence):
    sources = json.loads((evidence.parent / 'SOURCES.json').read_text())
    required = {str((folder / part).relative_to(ROOT))
                for part in ('manifest.json', manifest['kernel'])}
    if not required <= set(sources):
        raise RuntimeError(f'{folder.name}: missing source provenance')
    for source, expected in sources.items():
        path = (ROOT / source).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'{folder.name}: hardware-tested source has changed: {source}')


def check_binary(folder, evidence, expected_hash):
    manifest = json.loads((folder / 'manifest.json').read_text())
    artifact = folder / 'build' / (manifest['filename'] + '.ZD2')
    original = (evidence.parent / 'BUILT.ZD2').read_bytes()
    if hashlib.sha256(original).hexdigest() != expected_hash:
        raise RuntimeError(f'{folder.name}: recorded hardware-tested binary hash differs')
    if artifact.read_bytes() == original:
        return None
    from artwork import check_variant
    try:
        return check_variant(original, artifact.read_bytes(), artifact.with_suffix('.ZIC').read_bytes(),
                             ROOT / 'src/msplus/artwork' / (folder.name + '.png'))
    except (ValueError, FileNotFoundError) as error:
        raise RuntimeError(f'{folder.name}: current build differs from the hardware-tested binary: {error}') from error


def qualified_artifacts(report):
    folders = {p.parent.name: p.parent for p in (ROOT / 'src/msplus').glob('*/manifest.json')
               if p.parent.name not in {'gain', 'calibrate', 'meminfo', 'linearity'}}
    rows = report['ports']
    if len(rows) != len(folders) or {r['port'] for r in rows} != set(folders):
        raise RuntimeError('Evidence must cover exactly the complete musical set, without duplicates')
    artifacts = {}
    for row in rows:
        name = row['port']
        folder = folders[name]
        manifest = json.loads((folder / 'manifest.json').read_text())
        artifact = folder / 'build' / (manifest['filename'] + '.ZD2')
        evidence = (ROOT / row['evidence']).resolve()
        if not evidence.is_relative_to(ROOT):
            raise RuntimeError('Evidence must be inside the working repository')
        check_measurements(name, evidence)
        check_binary(folder, evidence, row['tested_binary_sha256'])
        check_sources(folder, manifest, evidence)
        if not (folder / 'build/REPORT.md').is_file():
            raise RuntimeError(f'{name}: upstream build validation report missing')
        artifacts[name] = artifact
    return artifacts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backup', required=True, type=Path)
    ap.add_argument('--evidence', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    artifacts = qualified_artifacts(json.loads(args.evidence.read_text()))
    verify_backup(args.backup)
    args.output.mkdir(parents=True, exist_ok=False)
    # Check every container/icon locally before the first real install.
    for name, artifact in sorted(artifacts.items()):
        output = args.output / name
        output.mkdir()
        upstream_operation(output, 'install', artifact, dry=True)
    preflight(args.backup.resolve(), args.output)
    for name, artifact in sorted(artifacts.items()):
        print(f'{name}: installing qualified binary and icon', flush=True)
        upstream_operation(args.output / name, 'install', artifact)
    # Read back every binary/icon, verify the entire catalogue and saved bank.
    with (args.output / 'audit.log').open('w') as log:
        subprocess.run([sys.executable, str(ROOT / 'tools/msplus/verify.py'),
                        str(args.backup.resolve()), str((args.output / 'audit').resolve()),
                        '--installed', *sorted(artifacts)], stdout=log, stderr=subprocess.STDOUT, check=True)
    final = args.output / 'final-health'
    final.mkdir()
    preflight(args.backup.resolve(), final)
    (args.output / 'INSTALLED.json').write_text(json.dumps({name: hashlib.sha256(path.read_bytes()).hexdigest()
                                                          for name, path in sorted(artifacts.items())}, indent=2) + '\n')
    print(f'{len(artifacts)} musical effects retained; stock scratch, saved bank and audio verified. Autosave OFF.', flush=True)


if __name__ == '__main__':
    main()
