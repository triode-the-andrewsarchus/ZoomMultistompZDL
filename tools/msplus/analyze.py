#!/usr/bin/env python3
"""Compare HIL captures to their stock-bypass reference; never opens hardware."""
import argparse
import json
from functools import partial
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from native import MATU_PORTS
from reference import validate_linearity, compare_scorch
from wavefold_reference import validate_hardware as validate_wavefold, compare_native, mono_input

NATIVE_CHECKS = {'scorch': compare_scorch, 'wavefold': compare_native}


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


def tone_metrics(directory, mono=False, mono_channel=0):
    audio, rate = sf.read(directory / 'return.wav', always_2d=True)
    metrics = []
    for ch in range(2):
        start = int((0.8 + mono_channel*2.5 if mono else 0.8 + ch * 2.5) * rate)
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


def load_captures(directory, reference, rate, mono=False, mono_channel=0):
    results = {}
    for folder in sorted(directory.iterdir()):
        if folder.name in ('baseline', 'restored') or not (folder / 'return.wav').is_file():
            continue
        report = json.loads((folder / 'report.json').read_text())
        if report['xruns'] or not report['finite'] or report['clipped']:
            raise SystemExit(f'Invalid capture: {folder}')
        if report['kind'] == 'tone':
            results[folder.name] = tone_metrics(folder, mono, mono_channel)
            continue
        audio, actual_rate = sf.read(folder / 'return.wav', always_2d=True)
        if actual_rate != rate:
            raise SystemExit('Capture rates differ')
        if report['kind'] == 'sweep':
            ref = np.repeat(reference[:, mono_channel:mono_channel+1], 2, axis=1) if mono else reference
            results[folder.name] = compare(ref, audio, rate)
        else:
            results[folder.name] = dict(peak=np.max(abs(audio), axis=0).tolist(),
                                        rms=np.sqrt(np.mean(audio**2, axis=0)).tolist())
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


def tone_peaks(audio, rate, channel, centers):
    start = int((0.8 + channel * 2.5) * rate)
    segment = audio[start:start + int(0.8 * rate), channel]
    freq, power = signal.periodogram(segment, fs=rate, window='hann',
                                     nfft=2 ** 20, scaling='spectrum')
    rows = []
    for expected in centers:
        band = np.abs(freq - expected) < 20
        index = int(np.argmax(power[band]))
        rows.append(dict(channel=channel, expected_hz=expected,
                         measured_hz=float(freq[band][index]),
                         power_dbfs=float(10 * np.log10(max(power[band][index], 1e-30)))))
    return rows


def validate_ring(directory):
    audio, rate = sf.read(directory / 'wet/return.wav', always_2d=True)
    rows, errors = [], []
    for ch, carrier in enumerate([400.4 * 1.006, 400.4]):
        rows.extend(tone_peaks(audio, rate, ch, [997 - carrier, 997 + carrier]))
    for row in rows:
        if abs(row['measured_hz'] - row['expected_hz']) > 1:
            errors.append(f'Klang sideband mismatch: {row}')
    return rows, errors


def validate_tracking(directory):
    audio, rate = sf.read(directory / 'tone/return.wav', always_2d=True)
    rows, errors = [], []
    for ch in range(2):
        rows.extend(tone_peaks(audio, rate, ch, [498.5, 997, 1994]))
    for row in rows:
        if abs(row['measured_hz'] - row['expected_hz']) > 3 or row['power_dbfs'] < -75:
            errors.append(f'Corrupt master/sub/harmony tracking mismatch: {row}')
    return rows, errors


def validate_dry(directory, reference, effect, mono_channel=0):
    audio, rate = sf.read(directory / 'dry/return.wav', always_2d=True)
    if effect == 'klang':
        reference, _ = sf.read(directory / 'baseline-tone/return.wav', always_2d=True)
    if effect in MATU_PORTS:
        reference = np.repeat(reference[:, mono_channel:mono_channel+1], 2, axis=1)
    expected = -6.0206 if effect in ('scorch', 'genloss', 'hydra', 'spiral', 'rewire', 'gyre') else 0
    return [f'{effect} dry gain mismatch: {row}' for row in compare(reference, audio, rate)
            if abs(row['gain_db'] - expected) > 0.5]


def validate_hold(directory, labels, tone=True, first=False):
    baseline, rate = sf.read(directory / 'baseline/return.wav', always_2d=True)
    noise = np.sqrt(np.mean(baseline[-rate:]**2, axis=0))
    rows, errors = [], []
    for label in labels:
        audio, _ = sf.read(directory / label / 'return.wav', always_2d=True)
        segment = audio[:rate] if first else audio[-rate:]
        rms = np.sqrt(np.mean(segment**2, axis=0))
        row = dict(capture=label, rms=rms.tolist(), above_noise_db=(20*np.log10(np.maximum(rms, 1e-12)/noise)).tolist())
        rows.append(row)
        if np.any(rms < noise*5):
            errors.append(f'{label}: held/generated audio is too quiet: {row}')
        if tone:
            peaks = [r for ch in range(2) for r in tone_peaks(audio, rate, ch, [997])]
            row['peaks'] = peaks
            if any(abs(r['measured_hz']-997) > 3 for r in peaks):
                errors.append(f'{label}: held tone frequency mismatch: {peaks}')
    return rows, errors



def validate_modulation(directory, label):
    audio, rate = sf.read(directory / label / 'return.wav', always_2d=True)
    start, end = int(.5*rate), int(5.5*rate)
    size = int(.05*rate)
    windows = audio[start:end].reshape(-1, size, 2)
    rms = np.sqrt(np.mean(windows**2, axis=1))
    lo, hi = np.percentile(rms, [10, 90], axis=0)
    depth = 20*np.log10(np.maximum(hi, 1e-12)/np.maximum(lo, 1e-12))
    row = dict(capture=label, envelope_depth_db=depth.tolist())
    return row, [f'{label}: modulation depth too small: {row}'] if np.any(depth < 3) else []


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


def validate_activity(directory):
    """A stable, unclipped recording is not proof that a kernel produced audio."""
    baseline, rate = sf.read(directory / 'baseline/return.wav', always_2d=True)
    noise = np.sqrt(np.mean(baseline[-rate:]**2, axis=0))
    rows, errors = [], []
    for path in sorted(directory.glob('*/report.json')):
        label = path.parent.name
        report = json.loads(path.read_text())
        if label.startswith('baseline') or label in ('dry', 'zero') or report['kind'] == 'silence':
            continue
        audio, _ = sf.read(path.parent / 'return.wav', always_2d=True)
        rms = np.sqrt(np.mean(audio**2, axis=0))
        row = dict(capture=label, above_noise_db=(20*np.log10(np.maximum(rms, 1e-12)/noise)).tolist())
        rows.append(row)
        if np.any(rms < noise*5):
            errors.append(f'{label}: no reliable musical output above the noise floor: {row}')
    return rows, errors


# Effect-specific evidence stays next to its test function, rather than adding
# another branch to the orchestration for each new port.
EFFECT_CHECKS = {
    'linearity': ('output_linearity', 'known_amplitude_output_linearity', validate_linearity),
    'corrupt': ('tracking', 'master_sub_harmony_frequencies', validate_tracking),
    'klang': ('sidebands', 'ring_sideband_frequencies', validate_ring),
    'stasis': ('held_or_generated_audio', 'held_or_generated_audio',
               partial(validate_hold, labels=['hold', 'hold-off'])),
    'scrub': ('held_or_generated_audio', 'held_or_generated_audio',
              partial(validate_hold, labels=['wet'], tone=False)),
    'griddly': ('held_or_generated_audio', 'held_or_generated_audio',
                partial(validate_hold, labels=['tail'], tone=False, first=True)),
    'dubsiren': ('held_or_generated_audio', 'held_or_generated_audio',
                 partial(validate_hold, labels=['siren'], tone=False, first=True)),
    'wavefold': ('folded_tone', 'configurable_wavefolding_and_voices', validate_wavefold),
    'eugate': ('modulation', 'rhythm_envelope_modulation', partial(validate_modulation, label='wet')),
    'breather': ('modulation', 'rhythm_envelope_modulation', partial(validate_modulation, label='pump')),
}


def verify_effect(directory, effect, calibration=None, output_probe=None):
    """Run the effect-specific reference and signature validation phase."""
    results, errors, checks = {}, [], []
    if calibration and effect in NATIVE_CHECKS:
        rows, problems = NATIVE_CHECKS[effect](directory, calibration, output_probe)
        results['software_reference'] = rows
        errors.extend(problems)
        checks.append('native_DSP_harmonics')
    if effect in EFFECT_CHECKS:
        key, label, validate = EFFECT_CHECKS[effect]
        rows, problems = validate(directory)
        results[key] = rows
        errors.extend(problems)
        checks.append(label)
    return results, errors, checks


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--gain-check', action='store_true')
    ap.add_argument('--calibration', type=Path)
    ap.add_argument('--output-probe', type=Path, help='Completed bounded output-linearity HIL directory')
    ap.add_argument('--effect', choices=['gain', 'linearity', 'flower', 'klang', 'scorch', 'corrupt', 'howl', 'dustbox', 'genloss', 'microloom', 'shatter', 'arrakis', 'taffy', 'dissolve', 'mangle', 'rooms', 'hydra', 'spiral', 'stasis', 'rewire', 'gyre', 'galactic', 'spool', 'oxide'] + list(MATU_PORTS))
    args = ap.parse_args()
    reference, rate = sf.read(args.directory / 'baseline/return.wav', always_2d=True)
    lane = mono_input(args.directory) if args.effect == 'wavefold' else 0
    results = load_captures(args.directory, reference, rate, args.effect in MATU_PORTS, lane)
    errors = validate_gain(args.directory, reference, results) if args.gain_check else []
    checks = ['capture_integrity']
    rows, problems = validate_activity(args.directory)
    results['signal_activity'] = rows
    errors.extend(problems)
    checks.append('signal_above_noise')
    if args.gain_check or args.effect == 'gain':
        errors = validate_gain(args.directory, reference, results)
        checks.append('gain_curve')
    if (args.directory / 'dry/return.wav').is_file():
        errors.extend(validate_dry(args.directory, reference, args.effect, lane))
        checks.append('dry_path_gain')
    effect_results, effect_errors, effect_checks = verify_effect(
        args.directory, args.effect, args.calibration, args.output_probe)
    results.update(effect_results)
    errors.extend(effect_errors)
    checks.extend(effect_checks)
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
