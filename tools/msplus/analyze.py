#!/usr/bin/env python3
"""Compare HIL captures to their stock-bypass reference; never opens hardware."""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal


def align(reference, actual, rate):
    corr = signal.correlate(actual, reference, mode='full', method='fft')
    lags = signal.correlation_lags(len(actual), len(reference))
    allowed = np.abs(lags) < int(0.1 * rate)
    lag = int(lags[allowed][np.argmax(np.abs(corr[allowed]))])
    start = max(0, lag)
    ref_start = max(0, -lag)
    n = min(len(reference) - ref_start, len(actual) - start)
    return reference[ref_start:ref_start + n], actual[start:start + n], lag


def compare(reference, actual, rate):
    results = []
    for ch in range(2):
        ref, out, lag = align(reference[:, ch], actual[:, ch], rate)
        gain = float(np.dot(ref, out) / np.dot(ref, ref))
        error = out - gain * ref
        residual = 20 * np.log10(max(np.linalg.norm(error), 1e-15) / max(np.linalg.norm(out), 1e-15))
        ref_fft = np.fft.rfft(ref)
        out_fft = np.fft.rfft(out)
        freq = np.fft.rfftfreq(len(ref), 1 / rate)
        response = []
        for center in [50, 100, 200, 400, 800, 1600, 3200, 6400, 12800]:
            band = (freq > center / 2 ** (1 / 6)) & (freq < center * 2 ** (1 / 6))
            ratio = np.sum(np.abs(out_fft[band]) ** 2) / max(np.sum(np.abs(ref_fft[band]) ** 2), 1e-30)
            response.append([center, float(10 * np.log10(max(ratio, 1e-30)))])
        results.append(dict(channel=ch, gain_db=float(20 * np.log10(max(abs(gain), 1e-15))),
                            relative_lag_samples=lag, residual_db=float(residual),
                            rms_dbfs=float(20 * np.log10(max(np.sqrt(np.mean(out ** 2)), 1e-15))),
                            response_db=response))
    return results


def tone_metrics(directory):
    audio, rate = sf.read(directory / 'return.wav', always_2d=True)
    metrics = []
    for ch in range(2):
        start = int((0.8 + ch * 2.5) * rate)
        segment = audio[start:start + int(0.8 * rate), ch]
        freq = np.fft.rfftfreq(len(segment), 1 / rate)
        power = np.abs(np.fft.rfft(segment * signal.windows.hann(len(segment)))) ** 2
        def band(harmonic):
            return float(power[np.abs(freq - 997 * harmonic) < 8].sum())
        fundamental = band(1)
        harmonic = sum(band(i) for i in range(2, 6))
        metrics.append(dict(channel=ch, thd_db=float(10 * np.log10(max(harmonic, 1e-30) / max(fundamental, 1e-30))),
                            peak=float(np.max(np.abs(segment)))))
    return metrics


def load_captures(directory, reference, rate):
    results = {}
    for folder in sorted(directory.iterdir()):
        if folder.name == 'baseline' or not (folder / 'return.wav').is_file():
            continue
        report = json.loads((folder / 'report.json').read_text())
        if report['xruns'] or not report['finite'] or report['clipped']:
            raise SystemExit(f'Invalid capture: {folder}')
        if report['kind'] == 'tone':
            results[folder.name] = tone_metrics(folder)
            continue
        audio, actual_rate = sf.read(folder / 'return.wav', always_2d=True)
        if actual_rate != rate:
            raise SystemExit('Capture rates differ')
        results[folder.name] = compare(reference, audio, rate)
    return results


def validate_gain(directory, reference, results):
    errors = []
    for name, expected in [('unity', 0), ('half', -6.0206), ('quarter', -12.0412), ('bypass', 0)]:
        if name not in results:
            errors.append(f'{name}: missing capture')
            continue
        for row in results[name]:
            if abs(row['gain_db'] - expected) > 0.5:
                errors.append(f"{name} channel {row['channel']}: gain {row['gain_db']:.3f} dB")
    if 'zero' not in results:
        errors.append('zero: missing capture')
    else:
        baseline_rms = np.sqrt(np.mean(reference ** 2, axis=0))
        zero, _ = sf.read(directory / 'zero/return.wav', always_2d=True)
        attenuation = 20 * np.log10(np.sqrt(np.mean(zero ** 2, axis=0)) / baseline_rms)
        if np.any(attenuation > -35):
            errors.append(f'Zero setting insufficient attenuation: {attenuation.tolist()}')
    return errors


def validate_ring(directory):
    audio, rate = sf.read(directory / 'wet/return.wav', always_2d=True)
    rows, errors = [], []
    # Hardware validation established B->input 3 and A->input 4 on this rig.
    for ch, carrier in enumerate([400.4 * 1.006, 400.4]):
        segment = audio[int((0.8 + ch * 2.5) * rate):int((1.6 + ch * 2.5) * rate), ch]
        nfft = 2 ** 20
        freq = np.fft.rfftfreq(nfft, 1 / rate)
        magnitude = abs(np.fft.rfft(segment * np.hanning(len(segment)), n=nfft))
        for expected in [997 - carrier, 997 + carrier]:
            band = np.abs(freq - expected) < 10
            measured = float(freq[band][np.argmax(magnitude[band])])
            rows.append(dict(channel=ch, expected_hz=expected, measured_hz=measured))
            if abs(measured - expected) > 1:
                errors.append(f'Klang channel {ch}: sideband {measured:.2f}, expected {expected:.2f}')
    return rows, errors


def check_silence(directory):
    audio, rate = sf.read(directory / 'silence/return.wav', always_2d=True)
    first = np.sqrt(np.mean(audio[:rate] ** 2, axis=0))
    last = np.sqrt(np.mean(audio[-rate:] ** 2, axis=0))
    growth = 20 * np.log10(np.maximum(last, 1e-8) / np.maximum(first, 1e-8))
    errors = []
    if np.max(abs(audio)) > 0.1:
        errors.append('Unexpectedly hot output with zero stimulus')
    if np.any(growth > 12):
        errors.append('Output grows by more than 12 dB during zero stimulus')
    return dict(peak=np.max(abs(audio), axis=0).tolist(), growth_db=growth.tolist()), errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--gain-check', action='store_true')
    ap.add_argument('--effect', choices=['gain', 'flower', 'klang', 'scorch', 'corrupt', 'howl'])
    args = ap.parse_args()
    reference, rate = sf.read(args.directory / 'baseline/return.wav', always_2d=True)
    results = load_captures(args.directory, reference, rate)
    errors = validate_gain(args.directory, reference, results) if args.gain_check else []
    checks = ['capture_integrity']
    if args.gain_check or args.effect == 'gain':
        errors = validate_gain(args.directory, reference, results)
        checks.append('gain_curve')
    if args.effect == 'klang':
        rows, problems = validate_ring(args.directory)
        results['sidebands'] = rows
        errors.extend(problems)
        checks.append('ring_sideband_frequencies')
    if (args.directory / 'silence/return.wav').exists():
        rows, problems = check_silence(args.directory)
        results['silence_stability'] = rows
        errors.extend(problems)
        checks.append('zero_input_stability')
    summary = dict(results=results, checks=checks, errors=errors, passed=not errors)
    (args.directory / 'analysis.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
