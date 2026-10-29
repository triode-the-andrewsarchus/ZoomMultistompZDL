#!/usr/bin/env python3
"""Calibrate bus-to-return scaling and compare Scorch hardware to native DSP."""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from native import Kernel, ROOT
from audio import verify_restored_audio


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


def validate_linearity(directory):
    """Measure return gain versus known DSP peaks; no correction is fitted away."""
    baseline, rate = sf.read(directory / 'baseline/return.wav', always_2d=True)
    noise = np.mean(baseline[-rate:]**2, axis=0)
    rows, errors = [], []
    quiet_gain = None
    for level in (1, 2, 5, 10, 25, 50, 75, 100):
        audio, actual_rate = sf.read(directory / f'peak{level:02}/return.wav', always_2d=True)
        if actual_rate != rate:
            raise ValueError('Linearity capture rates differ')
        if not np.isfinite(audio).all():
            return [], ['Non-finite output-probe samples']
        rms = np.sqrt(np.maximum(np.mean(audio[rate//2:5*rate]**2, axis=0) - noise, 0))
        peak = .55 * level/100
        gain = rms/(peak/np.sqrt(3))
        if quiet_gain is None:
            if not np.isfinite(gain).all() or np.any(rms < 5*np.sqrt(noise)) or np.any((gain < .5) | (gain > 2)):
                return [], ['Quiet diagnostic amplitude is missing or inconsistent with the calibrated rig']
            quiet_gain = gain
        change = 20*np.log10(np.maximum(gain, 1e-15)/np.maximum(quiet_gain, 1e-15))
        row = dict(level=level, dsp_peak=peak, bus_to_return_gain=gain.tolist(),
                   change_from_quiet_db=change.tolist())
        rows.append(row)
        if np.any(abs(change) > .5):
            errors.append(f'Output stage gain changes by more than 0.5 dB: {row}')
    return rows, errors


def harmonic_rms(samples, rate, frequency, count=10):
    """Fit harmonics together so arbitrary capture phase cannot leak between them.

    Each tone has both sine/cosine terms and the fit includes DC. Independent
    single-tone fits are biased when a noninteger-period window contains a much
    louder fundamental or other harmonics, particularly for Scorch's weak H4.
    """
    if count < 1 or frequency <= 0 or frequency * count >= rate / 2:
        raise ValueError('Harmonics must be positive and below Nyquist')
    t = np.arange(len(samples)) / rate
    basis = np.column_stack([wave(2 * np.pi * frequency * harmonic * t)
                             for harmonic in range(1, count + 1)
                             for wave in (np.sin, np.cos)] + [np.ones(len(t))])
    coeff, *_ = np.linalg.lstsq(basis, samples, rcond=None)
    return np.hypot(coeff[:-1:2], coeff[1:-1:2]) / np.sqrt(2)


def linear_output_limit(directory):
    """Find a contiguous measured range within 0.1 dB of the quiet output gain."""
    for level in (1, 2, 5, 10, 25, 50, 75, 100):
        report = json.loads((directory / f'peak{level:02}/report.json').read_text())
        if report['xruns'] or not report['finite'] or report['clipped']:
            raise ValueError('Invalid output-probe recording')
    rows, _ = validate_linearity(directory)
    if len(rows) != 8:
        raise ValueError('Output probe lacks a valid quiet reference')
    peak = 0
    for row in rows:
        changes = np.asarray(row['change_from_quiet_db'])
        if not np.isfinite(changes).all():
            raise ValueError('Invalid output-probe gain')
        if np.any(abs(changes) > .1):
            break
        peak = row['dsp_peak']
    return peak, np.asarray(rows[0]['bus_to_return_gain'])


def compare_scorch_capture(directory, gains, capture, mix, linear_peak=None):
    base, rate = sf.read(directory / 'baseline-tone/return.wav', always_2d=True)
    actual, actual_rate = sf.read(directory / capture / 'return.wav', always_2d=True)
    if actual_rate != rate:
        raise ValueError('Reference rates differ')
    base_level = json.loads((directory / 'baseline-tone/report.json').read_text())['level_db']
    test_level = json.loads((directory / capture / 'report.json').read_text())['level_db']
    scaling = 10 ** ((test_level - base_level) / 20)
    rows, errors = [], []
    for ch in range(2):
        start = int((0.8 + ch * 2.5) * rate)
        recorded = actual[start:start + int(0.8 * rate), ch]
        original = base[start:start + len(recorded), ch]
        amplitude = harmonic_rms(original, rate, 997, count=1)[0] * np.sqrt(2) * scaling / gains[ch]
        kernel = Kernel('scorch')
        kernel.coeff[5:7] = [1, mix]  # Keep maximum Gain in both reference captures.
        count = 44160
        t = np.arange(count) / 44100
        samples = np.zeros((count, 2))
        samples[:, 1 - ch] = amplitude * np.sin(2 * np.pi * 997 * t)
        predicted = np.concatenate([kernel.block(b) for b in samples.reshape(-1, 16, 2)])
        predicted = predicted[-35280:, 1 - ch]
        dsp_peak = float(np.max(abs(predicted)))
        in_range = linear_peak is None or dsp_peak <= linear_peak
        predicted = predicted * gains[ch]
        predicted_levels = harmonic_rms(predicted, 44100, 997)
        recorded_levels = harmonic_rms(recorded, rate, 997)
        for harmonic in range(1, 6):
            expected = float(predicted_levels[harmonic - 1])
            measured = float(recorded_levels[harmonic - 1])
            error_db = float(20 * np.log10(max(measured, 1e-15) / max(expected, 1e-15)))
            rows.append(dict(channel=ch, harmonic=harmonic, predicted_rms=expected,
                             measured_rms=measured, error_db=error_db, capture=capture,
                             dsp_peak=dsp_peak, measured_linear_limit=linear_peak,
                             comparison_domain='linear' if in_range else 'outside_measured_linear_range'))
            # Harmonics close to the ADC noise floor cannot be compared reliably.
            limit = 1 if harmonic == 1 else 3
            if in_range and expected > 0.00005 and abs(error_db) > limit:
                errors.append(f'Scorch reference mismatch: {rows[-1]}')
    return rows, errors


def compare_scorch(directory, calibration, output_probe=None):
    gains = np.asarray(json.loads(calibration.read_text())['bus_to_return'])
    if gains.shape != (2,) or not np.isfinite(gains).all() or np.any((gains < .5) | (gains > 2)):
        raise ValueError('Invalid bus-to-return calibration gains')
    if output_probe is None:
        return compare_scorch_capture(directory, gains, 'tone', 1)
    verify_restored_audio(output_probe, ROOT)
    linear_peak, quiet_gains = linear_output_limit(output_probe)
    if np.any(abs(20*np.log10(quiet_gains/gains)) > .2):
        raise ValueError('Output probe and calibration gains differ; recalibrate the rig')
    cases = {name: (dict(edits), kind) for name, edits, kind in
             json.loads((directory / 'CASES.json').read_text())}
    if cases.get('tone') != ({2: 100, 3: 100}, 'tone') or cases.get('tone-reference') != ({2: 100, 3: 50}, 'tone'):
        raise ValueError('Scorch reference requires explicit maximum Gain with Mix=100 and Mix=50')
    rows, errors = compare_scorch_capture(directory, gains, 'tone', 1, linear_peak)
    reference, problems = compare_scorch_capture(directory, gains, 'tone-reference', .5, linear_peak)
    if not all(row['comparison_domain'] == 'linear' for row in reference):
        errors.append('Scorch reference capture exceeds the independently measured linear output range')
    for row in rows + reference:
        row['output_probe'] = str(output_probe)
    return rows + reference, errors + problems


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
