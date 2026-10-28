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


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--gain-check', action='store_true')
    args = ap.parse_args()
    reference, rate = sf.read(args.directory / 'baseline/return.wav', always_2d=True)
    results = {}
    for folder in sorted(args.directory.iterdir()):
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
    errors = []
    if args.gain_check:
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
            zero, _ = sf.read(args.directory / 'zero/return.wav', always_2d=True)
            attenuation = 20 * np.log10(np.sqrt(np.mean(zero ** 2, axis=0)) / baseline_rms)
            if np.any(attenuation > -35):
                errors.append(f'Zero setting insufficient attenuation: {attenuation.tolist()}')
    summary = dict(results=results, errors=errors, passed=not errors)
    (args.directory / 'analysis.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
