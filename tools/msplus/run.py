#!/usr/bin/env python3
"""Run guarded install/audition/analyze/uninstall for explicitly named ports.

No retries. An unverified transfer or failed temp-patch restoration stops the
campaign, leaving the pedal powered and the effect installed for diagnosis.
Each install/removal is a separate upstream operation, with dry run and logs.
"""
import argparse
import fcntl
import json
import subprocess
import sys
from pathlib import Path

from upstream import ROOT, STOMPHACKS
from audition import TempPatch, verify_backup
from audio import physical_ports
from pedal_common import editor_off


def upstream_operation(output, operation, artifact, dry=False):
    command = [sys.executable, str(STOMPHACKS / 'tools-pedal/pedal_diy.py'), operation, str(artifact)]
    if dry:
        command.append('--dry-run')
    label = operation + ('-dry' if dry else '')
    with open('/tmp/ZoomMultistompZDL-midi.lock', 'w') as lock, (output / f'{label}.log').open('w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{label} failed, exit {result.returncode}; inspect {output / (label + ".log")}. '
                           'No further pedal commands will be sent. Keep powered if transfer safety is unverified.')


def run_effect(name, backup, output, calibration=None):
    effect = ROOT / 'src/msplus' / name
    manifest = json.loads((effect / 'manifest.json').read_text())
    artifact = effect / 'build' / (manifest['filename'] + '.ZD2')
    if not artifact.exists() or not (effect / 'build/REPORT.md').is_file():
        raise RuntimeError(f'Build and validate {name} first with tools/msplus/build.py')
    output.mkdir()
    print(f'{name}: checking install', flush=True)
    upstream_operation(output, 'install', artifact, dry=True)
    upstream_operation(output, 'install', artifact)
    print(f'{name}: installed, starting checked audition', flush=True)
    hil = output / 'hil'
    with (output / 'audition.log').open('w') as log:
        result = subprocess.run([sys.executable, str(ROOT / 'tools/msplus/audition.py'),
                                 str(effect), str(backup), str(hil)], stdout=log, stderr=subprocess.STDOUT)
    if not (hil / 'RESTORED').exists():
        raise RuntimeError(f'{name}: no verified restoration marker. STOP; inspect {output / "audition.log"}. '
                           'Effect remains installed. Do not power-cycle or issue further commands blindly.')
    # Only a verified stock temp patch permits removing its binary. Even an
    # ordinary audio failure gets this cleanup, but never an uncertain restore.
    upstream_operation(output, 'uninstall', artifact, dry=True)
    upstream_operation(output, 'uninstall', artifact)
    if result.returncode:
        raise RuntimeError(f'{name}: audio audition failed; stock restored and effect removed. See {output / "audition.log"}')
    analysis = [sys.executable, str(ROOT / 'tools/msplus/analyze.py'), str(hil), '--effect', name]
    if calibration is not None:
        analysis.extend(['--calibration', str(calibration)])
    with (output / 'analysis.log').open('w') as log:
        checked = subprocess.run(analysis, stdout=log, stderr=subprocess.STDOUT)
    if checked.returncode:
        raise RuntimeError(f'{name}: analysis failed; effect removed. See {output / "analysis.log"}')
    print(f'{name}: configured checks PASS; stock restored, saved patches unchanged, effect removed', flush=True)


def preflight(backup, output):
    # Fail before installation if audio routing or the scratch patch is wrong.
    physical_ports([f'AF16Rig Audio Pro:playback_AUX{i}' for i in (6, 7)],
                   [f'AF16Rig Audio Pro:capture_AUX{i}' for i in (2, 3)])
    with open('/tmp/ZoomMultistompZDL-midi.lock', 'w') as lock, (output / 'preflight.log').open('w') as log:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        session = TempPatch(log, backup)
        try:
            session.verify_saved()
        finally:
            editor_off(session.pedal)
            session.pedal.disconnect()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backup', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--calibration', type=Path, help='Enable calibrated Scorch harmonic comparison')
    ap.add_argument('effects', nargs='+')
    args = ap.parse_args()
    available = {p.parent.name for p in (ROOT / 'src/msplus').glob('*/manifest.json')}
    unknown = set(args.effects) - available
    if unknown or 'calibrate' in args.effects:
        ap.error('Choose musical ports only: ' + ', '.join(sorted(available - {'calibrate'})))
    if args.calibration is not None:
        args.calibration = args.calibration.resolve()
        json.loads(args.calibration.read_text())
    verify_backup(args.backup)
    args.output.mkdir(parents=True, exist_ok=False)
    preflight(args.backup.resolve(), args.output)
    for name in args.effects:
        run_effect(name, args.backup.resolve(), args.output / name, args.calibration)
    (args.output / 'COMPLETE').write_text('All requested configured checks passed and experimental effects were removed.\n')


if __name__ == '__main__':
    main()
