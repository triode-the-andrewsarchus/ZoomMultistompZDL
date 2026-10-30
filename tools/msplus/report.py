#!/usr/bin/env python3
"""Refresh hardware evidence using the same gates as retained installation.

Campaigns are explicitly ordered oldest to newest. An incomplete or failed new
attempt supersedes an older pass. This tool never opens MIDI or audio devices.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from upstream import ROOT
from install_set import check_measurements, check_sources, check_binary
from audio import require_loopback


def effect_row(folder, evidence):
    manifest = json.loads((folder / 'manifest.json').read_text())
    artifact = folder / 'build' / (manifest['filename'] + '.ZD2')
    row = dict(port=folder.name, display=manifest['display'], id=manifest['id'],
               family='Matujuice v1.5' if manifest.get('dependency') else 'original',
               build_report=str((folder / 'build/REPORT.md').relative_to(ROOT)),
               build_validated=(folder / 'build/REPORT.md').is_file(),
               current_build_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
               ready_for_retention=False, stock_baseline_healthy=False,
               status='Hardware evidence pending')
    if evidence is None:
        return row
    evidence = evidence.resolve()
    row['evidence'] = str(evidence.relative_to(ROOT))
    hil = evidence.parent
    row['audio_restoration_marker_present'] = (hil / 'AUDIO_RESTORED').is_file()
    if not evidence.is_file():
        row['status'] = 'UNQUALIFIED: latest hardware attempt has no completed analysis'
        return row
    analysis = json.loads(evidence.read_text())
    row.update(configured_checks=analysis['checks'], configured_passed=analysis['passed'],
               analysis_errors=analysis['errors'], capture_count=len(list(hil.glob('*/report.json'))),
               tested_binary_sha256=hashlib.sha256((hil / 'BUILT.ZD2').read_bytes()).hexdigest(),
               source_fingerprints=json.loads((hil / 'SOURCES.json').read_text()))
    try:
        require_loopback(json.loads((hil / 'baseline/report.json').read_text()))
        row['stock_baseline_healthy'] = True
        check_measurements(folder.name, evidence)
        check_sources(folder, manifest, evidence)
        artwork = check_binary(folder, evidence, row['tested_binary_sha256'])
        if artwork:
            row['artwork_only_variant'] = artwork
        row.update(ready_for_retention=True, status='PASS: selected standalone checks and current restoration/provenance gates')
    except (RuntimeError, FileNotFoundError, KeyError) as error:
        row.update(status='UNQUALIFIED: ' + str(error), qualification_error=str(error))
    return row


def test_log(path):
    match = re.search(r'Ran (\d+) tests? in [^\n]+\n\nOK\s*$', path.read_text())
    if match is None:
        raise ValueError('Test log does not end in a passing unittest result: ' + str(path))
    return dict(path=str(path.resolve().relative_to(ROOT)), tests=int(match[1]),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--previous', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--native-log', required=True, type=Path)
    ap.add_argument('--tools-log', required=True, type=Path)
    ap.add_argument('campaigns', nargs='+', type=Path)
    args = ap.parse_args()
    report = json.loads(args.previous.read_text())
    previous = {row['port']: row.get('evidence') for row in report['ports']}
    rows = []
    for manifest in sorted((ROOT / 'src/msplus').glob('*/manifest.json')):
        folder = manifest.parent
        if folder.name in {'gain', 'calibrate', 'meminfo', 'linearity'}:
            continue
        evidence = ROOT / previous[folder.name] if previous.get(folder.name) else None
        for campaign in args.campaigns:
            hil = campaign / folder.name / 'hil'
            if hil.is_dir():
                evidence = hil / 'analysis.json'
        rows.append(effect_row(folder, evidence))
    native, tools = test_log(args.native_log), test_log(args.tools_log)
    pending = [row['port'] for row in rows if not row['ready_for_retention']]
    report.update(ports=rows, native_tests=native['tests'], tool_fault_tests=tools['tests'],
                  verification_logs=dict(native=native, tools=tools),
                  current_blocker=dict(ports=pending, finding='Current qualification gates are incomplete' if pending else
                                       'All musical ports have current standalone hardware qualification'))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(rows)-len(pending)}/{len(rows)} ports meet current retention gates; pending: {", ".join(pending)}')


if __name__ == '__main__':
    main()
