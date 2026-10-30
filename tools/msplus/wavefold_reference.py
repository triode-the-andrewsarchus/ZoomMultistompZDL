"""WaveFold's redesigned response/voice checks and calibrated native comparison."""
import json
import hashlib
from pathlib import Path

import numpy as np
import soundfile as sf
from native import Kernel
from reference import harmonic_rms
from audio import analyze as analyze_audio


def mono_input(directory):
    """Discover the active input from both actual dry-path recordings."""
    folder=directory/'dry'
    report=json.loads((folder/'report.json').read_text())
    sent,rate=sf.read(folder/'send.wav',always_2d=True)
    returned,actual_rate=sf.read(folder/'return.wav',always_2d=True)
    if actual_rate!=rate or report['xruns']:
        raise ValueError('Invalid mono input routing capture')
    measured=analyze_audio(sent,returned,rate)
    if not measured['finite'] or measured['clipped']:
        raise ValueError('Non-finite or clipped mono routing recording')
    paths=[row for row in measured['paths'] if row['correlation']>.8 and -30<row['gain_db']<-10]
    identities=sorted((row['send'],row['capture']) for row in paths)
    advertised=sorted((row['send'],row['capture']) for row in report['paths']
                      if row['correlation']>.8 and -30<row['gain_db']<-10)
    if identities not in ([(0,0),(0,1)],[(1,0),(1,1)]) or advertised!=identities:
        raise ValueError('Dry recording does not prove one common mono input feeding both outputs')
    lane=identities[0][0]
    proof=dict(input_send=lane,paths=paths,sha256={name:hashlib.sha256((folder/name).read_bytes()).hexdigest()
                                                 for name in ('report.json','send.wav','return.wav')})
    (directory/'MONO_ROUTING.json').write_text(json.dumps(proof,indent=2)+'\n')
    return lane


def segment(directory, label, lane):
    report = json.loads((directory / label / 'report.json').read_text())
    if not report['finite'] or report['clipped'] or report['xruns']:
        raise ValueError('Invalid WaveFold capture: ' + label)
    audio, rate = sf.read(directory / label / 'return.wav', always_2d=True)
    start=.9+lane*2.5
    return audio[int(start*rate):int((start+.8)*rate)], rate


def reviewed_labels(directory):
    cases = {label: (edits, kind) for label, edits, kind in json.loads((directory / 'CASES.json').read_text())}
    labels = [f'd{drive}-s{sym:03}' for drive in (40,100) for sym in range(0,101,5)]
    stage_labels = [f'stage{stages}-voice{voice}' for stages in range(1,6) for voice in (0,1,2)]
    for label in labels:
        drive, sym = label[1:].split('-s')
        edits, kind = cases[label]
        if dict(edits).get(2) != int(drive) or dict(edits).get(3) != int(sym) or kind != 'tone':
            raise ValueError('WaveFold symmetry grid edits do not match the reviewed case')
    for label in stage_labels:
        stages, voice = label[5:].split('-voice')
        edits, kind = cases[label]
        if dict(edits).get(8) != int(stages)-1 or dict(edits).get(4) != int(voice) or kind != 'tone':
            raise ValueError('Stage/voice capture does not match reviewed selector edits')
    return labels + ['quiet','loud'] + stage_labels


def validate_hardware(directory):
    rows, errors = [], []
    lane=mono_input(directory)
    for label in reviewed_labels(directory):
        audio, rate = segment(directory, label, lane)
        for channel in range(2):
            levels = harmonic_rms(audio[:,channel], rate, 997)
            ratio = float(np.linalg.norm(levels[1:])/max(levels[0],1e-15))
            rows.append(dict(capture=label, channel=channel, harmonic_ratio=ratio))
            if ratio < .025:
                errors.append('WaveFold has a near-dry gap: ' + str(rows[-1]))
    ratios = []
    for label in ('voice-full','voice-low'):
        audio, rate = segment(directory, label, lane)
        channel_ratios = []
        for channel in range(2):
            levels = harmonic_rms(audio[:,channel], rate, 200, count=20)
            channel_ratios.append(float(levels[19]/max(levels[0],1e-15)))
        ratios.append(np.asarray(channel_ratios))
    difference = 20*np.log10(np.maximum(ratios[1],1e-15)/np.maximum(ratios[0],1e-15))
    rows.append(dict(check='input_voice_filter', high_to_low_change_db=difference.tolist()))
    if np.any(difference > -12):
        errors.append('LOW voice does not sufficiently reduce 4 kHz relative to 200 Hz')
    return rows, errors


def capture_coefficients(directory, kernel):
    coefficients = kernel.coeff.copy()
    rows = {}
    for label, edits, _ in json.loads((directory / 'CASES.json').read_text()):
        for parameter, value in edits:
            if parameter < 2:
                raise ValueError('Unexpected bypass/identity edit in WaveFold reference cases')
            index = parameter-2
            coefficients[index+5] = value/kernel.manifest['params'][index]['max']
        rows[label] = coefficients.copy()
    return rows


def compare_native(directory, calibration, output_probe=None):
    gains = np.asarray(json.loads(Path(calibration).read_text())['bus_to_return'])
    if gains.shape != (2,) or not np.isfinite(gains).all() or np.any((gains<.5)|(gains>2)):
        raise ValueError('Invalid WaveFold output calibration')
    lane=mono_input(directory)
    baseline, rate = segment(directory, 'baseline-tone', lane)
    amplitude = harmonic_rms(baseline[:,lane],rate,997,count=1)[0]*np.sqrt(2)/gains[lane]
    base_level = json.loads((directory/'baseline-tone/report.json').read_text())['level_db']
    kernel = Kernel('wavefold', arena_bytes=705600)
    coefficients = capture_coefficients(directory,kernel)
    rows, errors = [], []
    labels = ['wet','drive','quiet','loud','voice-fold','voice-blend'] + [f'd40-s{sym:03}' for sym in (5,35,65,95)] + [f'stage{stages}-voice1' for stages in range(1,6)]
    t=np.arange(44160)/44100
    for label in labels:
        actual, actual_rate = segment(directory,label,lane)
        if actual_rate != rate:
            raise ValueError('WaveFold reference capture sample rates differ')
        level = json.loads((directory/label/'report.json').read_text())['level_db']
        samples=np.column_stack([np.zeros(len(t)), amplitude*10**((level-base_level)/20)*np.sin(2*np.pi*997*t)])
        kernel.state[:]=0;kernel.state[kernel.guard_word]=kernel.guard;kernel.coeff[:]=coefficients[label]
        predicted=np.concatenate([kernel.block(b) for b in samples.reshape(-1,16,2)])[-35280:,1]
        expected=harmonic_rms(predicted,44100,997)
        for channel in range(2):
            measured=harmonic_rms(actual[:,channel],rate,997)
            for harmonic in range(10):
                target=float(expected[harmonic]*gains[channel])
                if target < .00005:
                    continue
                error=float(20*np.log10(max(measured[harmonic],1e-15)/target))
                row=dict(capture=label,channel=channel,harmonic=harmonic+1,
                         predicted_rms=target,measured_rms=float(measured[harmonic]),error_db=error)
                rows.append(row)
                if abs(error) > (1 if harmonic==0 else 3):
                    errors.append('WaveFold native/reference mismatch: '+str(row))
    if len(rows)<20:
        errors.append('Insufficient measurable WaveFold harmonics for native comparison')
    return rows, errors
