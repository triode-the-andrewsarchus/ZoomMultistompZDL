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


def decode_memory(directory):
    from scipy.signal import periodogram
    report = json.loads((directory / 'armed/report.json').read_text())
    if report['xruns'] or not report['finite'] or report['clipped']:
        raise ValueError('Invalid memory diagnostic capture')
    audio, rate = sf.read(directory / 'armed/return.wav', always_2d=True)
    def frequencies(at):
        segment = audio[int(at*rate):int((at+0.12)*rate)]
        freq, power = periodogram(segment, fs=rate, window='hann', nfft=2**18, axis=0)
        band = (freq > 150) & (freq < 5600)
        return freq[band][np.argmax(power[band], axis=0)]
    seen_preamble = False
    first = None
    for at in np.arange(0, 1, 0.05):
        preamble = np.max(abs(frequencies(at) - [300, 200])) < 2
        if preamble:
            seen_preamble = True
        elif seen_preamble:
            first = at + 0.2
            break
    if first is None:
        raise ValueError('No complete telemetry preamble')
    payload, rows = [], []
    for step in range(6):
        pair = frequencies(first + step*0.5)[::-1]  # bus A then B
        decoded = np.rint((pair - 400)/20).astype(int)
        if np.any(decoded < 0) or np.any(decoded > 255) or np.max(abs(pair - (400+20*decoded))) > 2:
            raise ValueError('Invalid telemetry byte frequencies')
        payload.extend(decoded.tolist())
        rows.append(pair.tolist())
    data = bytes(payload)
    base, end, count = [int.from_bytes(data[i:i+4], 'little') for i in (0, 4, 8)]
    if not base or end <= base or count != end-base or (base | end | count) & 3:
        raise ValueError('Descriptor is not a consistent aligned range')
    result = dict(base=base, exclusive_end=end, byte_count=count, frequencies_hz=rows,
                  arena_access='none; descriptor words read only')
    (directory / 'memory.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path, help='Completed calibration capture directory')
    ap.add_argument('--memory', action='store_true', help='Decode read-only memory descriptor telemetry')
    args = ap.parse_args()
    result = decode_memory(args.directory) if args.memory else calibrate(args.directory)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
