#!/usr/bin/env python3
"""Calibrate bus-to-return scaling and compare Scorch hardware to native DSP."""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from native import Kernel


def calibrate(directory):
    baseline, rate = sf.read(directory / 'baseline/return.wav', always_2d=True)
    noise_power = np.mean(baseline[-rate:] ** 2, axis=0)
    rows = {}
    for name, peak in [('peak50', 0.0005), ('peak10', 0.0001), ('volume10', 0.0005)]:
        report = json.loads((directory / name / 'report.json').read_text())
        if report['xruns'] or not report['finite'] or report['clipped']:
            raise ValueError('Invalid calibration recording: ' + name)
        audio, actual_rate = sf.read(directory / name / 'return.wav', always_2d=True)
        if actual_rate != rate:
            raise ValueError('Calibration rates differ')
        power = np.mean(audio[rate // 2:rate * 5] ** 2, axis=0)
        rms = np.sqrt(np.maximum(power - noise_power, 0))
        rows[name] = dict(rms=rms.tolist(), bus_to_return=(rms / (peak / np.sqrt(3))).tolist())
    result = dict(rate=rate, noise_rms=np.sqrt(noise_power).tolist(), results=rows,
                  bus_to_return=rows['peak50']['bus_to_return'])
    (directory / 'calibration.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def sine_rms(samples, rate, frequency):
    t = np.arange(len(samples)) / rate
    basis = np.column_stack((np.sin(2 * np.pi * frequency * t),
                             np.cos(2 * np.pi * frequency * t), np.ones(len(t))))
    coeff, *_ = np.linalg.lstsq(basis, samples, rcond=None)
    return float(np.hypot(coeff[0], coeff[1]) / np.sqrt(2))


def compare_scorch(directory, calibration):
    base, rate = sf.read(directory / 'baseline-tone/return.wav', always_2d=True)
    actual, actual_rate = sf.read(directory / 'tone/return.wav', always_2d=True)
    if actual_rate != rate:
        raise ValueError('Reference rates differ')
    base_level = json.loads((directory / 'baseline-tone/report.json').read_text())['level_db']
    test_level = json.loads((directory / 'tone/report.json').read_text())['level_db']
    scaling = 10 ** ((test_level - base_level) / 20)
    gains = json.loads(calibration.read_text())['bus_to_return']
    rows, errors = [], []
    for ch in range(2):
        start = int((0.8 + ch * 2.5) * rate)
        recorded = actual[start:start + int(0.8 * rate), ch]
        original = base[start:start + len(recorded), ch]
        amplitude = sine_rms(original, rate, 997) * np.sqrt(2) * scaling / gains[ch]
        kernel = Kernel('scorch')
        kernel.coeff[5:7] = [1, 1]  # reviewed tone case: Gain=100, Mix=100
        count = 44160
        t = np.arange(count) / 44100
        samples = np.zeros((count, 2))
        samples[:, 1 - ch] = amplitude * np.sin(2 * np.pi * 997 * t)
        predicted = np.concatenate([kernel.block(b) for b in samples.reshape(-1, 16, 2)])
        predicted = predicted[-35280:, 1 - ch] * gains[ch]
        for harmonic in range(1, 6):
            expected = sine_rms(predicted, 44100, 997 * harmonic)
            measured = sine_rms(recorded, rate, 997 * harmonic)
            error_db = float(20 * np.log10(max(measured, 1e-15) / max(expected, 1e-15)))
            rows.append(dict(channel=ch, harmonic=harmonic, predicted_rms=expected,
                             measured_rms=measured, error_db=error_db))
            # Harmonics close to the ADC noise floor cannot be compared reliably.
            limit = 1 if harmonic == 1 else 3
            if expected > 0.00005 and abs(error_db) > limit:
                errors.append(f'Scorch reference mismatch: {rows[-1]}')
    return rows, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path, help='Completed calibration capture directory')
    args = ap.parse_args()
    print(json.dumps(calibrate(args.directory), indent=2))


if __name__ == '__main__':
    main()
