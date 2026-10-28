#!/usr/bin/env python3
"""Explicit JACK/PipeWire send/return capture. No MIDI or interface mixer writes.

Discovery records every physical capture port, sending distinct probes to the
specified outputs only. Default peak is -50 dBFS. Connection names and xruns are
saved alongside WAVs; an xrun makes the run invalid. Outputs stop on exit.
"""
import argparse
import json
import threading
from pathlib import Path

import jack
import numpy as np
import soundfile as sf
from scipy import signal


def stimulus(rate, level_db, kind):
    amplitude = 10 ** (level_db / 20)
    n = int(rate * 6)
    result = np.zeros((n, 2), np.float32)
    rng = np.random.default_rng(70)
    for ch in range(2):
        start = int((0.5 + ch * 2.5) * rate)
        count = int(1.5 * rate)
        t = np.arange(count) / rate
        if kind == 'probe':
            wave = rng.uniform(-1, 1, count)
        elif kind == 'tone':
            wave = np.sin(2 * np.pi * 997 * t)
        else:
            wave = signal.chirp(t, f0=30, f1=18000, t1=1.5, method='logarithmic')
        wave *= signal.windows.tukey(count, 0.04)
        result[start:start + count, ch] = amplitude * wave
    return result


def capture(client, test, sends, returns):
    outputs = [client.outports.register(f'send_{i}') for i in range(2)]
    inputs = [client.inports.register(f'return_{i}') for i in range(len(returns))]
    recording = np.zeros((len(test), len(inputs)), np.float32)
    done = threading.Event()
    started = threading.Event()
    position = 0
    xruns = []

    @client.set_xrun_callback
    def on_xrun(delay):
        xruns.append(float(delay))

    @client.set_process_callback
    def process(frames):
        nonlocal position
        count = min(frames, len(test) - position) if started.is_set() else 0
        for ch, port in enumerate(outputs):
            buf = port.get_array()
            buf[:] = 0
            if count:
                buf[:count] = test[position:position + count, ch]
        for ch, port in enumerate(inputs):
            if count:
                recording[position:position + count, ch] = port.get_array()[:count]
        position += count
        if started.is_set() and position == len(test):
            done.set()

    with client:
        # Do not advance the stimulus until every explicit connection exists.
        for out, dest in zip(outputs, sends):
            client.connect(out, dest)
        for src, inp in zip(returns, inputs):
            client.connect(src, inp)
        done.clear()
        started.set()
        if not done.wait(len(test) / client.samplerate + 5):
            raise TimeoutError('JACK callback stalled')
    return recording, xruns


def analyze(test, recording, rate):
    """Per-path correlation, lag and gain; silence/clipping checked independently."""
    paths = []
    for send in range(test.shape[1]):
        x = test[:, send].astype(np.float64)
        for ret in range(recording.shape[1]):
            y = recording[:, ret].astype(np.float64)
            corr = signal.correlate(y, x, mode='full', method='fft')
            lag = int(np.argmax(np.abs(corr)) - (len(x) - 1))
            if lag < 0 or lag > rate:
                continue
            aligned = y[lag:]
            ref = x[:len(aligned)]
            gain = float(np.dot(ref, aligned) / max(np.dot(ref, ref), 1e-30))
            similarity = float(np.dot(ref, aligned) / max(np.linalg.norm(ref) * np.linalg.norm(aligned), 1e-30))
            paths.append(dict(send=send, capture=ret, latency_samples=lag,
                              latency_ms=1000 * lag / rate,
                              gain_db=20 * np.log10(max(abs(gain), 1e-15)),
                              correlation=similarity))
    peak = np.max(np.abs(recording), axis=0)
    return dict(paths=paths, peak=peak.tolist(),
                rms=np.sqrt(np.mean(recording ** 2, axis=0)).tolist(),
                finite=bool(np.isfinite(recording).all()),
                silent=bool(peak.max() < 1e-6), clipped=bool(peak.max() >= 0.98))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--send', nargs=2, required=True, help='Exact physical JACK port names')
    ap.add_argument('--return-ports', nargs='+', help='Exact physical capture ports; default: all AudioFuse ports')
    ap.add_argument('--level-db', type=float, default=-50)
    ap.add_argument('--kind', choices=['probe', 'tone', 'sweep'], default='probe')
    args = ap.parse_args()
    if not -80 <= args.level_db <= -20:
        ap.error('Level must be between -80 and -20 dBFS')
    args.directory.mkdir(parents=True, exist_ok=False)
    with jack.Client('zdl-hil', no_start_server=True) as discovery:
        sends = {p.name for p in discovery.get_ports(is_audio=True, is_physical=True, is_input=True)}
        returns = [p.name for p in discovery.get_ports(is_audio=True, is_physical=True, is_output=True)]
        if not set(args.send) <= sends:
            ap.error('Requested sends are not physical playback ports')
        chosen = args.return_ports or [p for p in returns if 'AF16Rig' in p]
        if not chosen or not set(chosen) <= set(returns):
            ap.error('Requested returns are not physical capture ports')
    client = jack.Client('zdl-hil', no_start_server=True)
    try:
        rate = client.samplerate
        test = stimulus(rate, args.level_db, args.kind)
        recording, xruns = capture(client, test, args.send, chosen)
    finally:
        client.close()
    sf.write(args.directory / 'send.wav', test, rate, subtype='FLOAT')
    sf.write(args.directory / 'return.wav', recording, rate, subtype='FLOAT')
    result = analyze(test, recording, rate)
    result.update(rate=rate, sends=args.send, returns=chosen, xruns=xruns,
                  level_db=args.level_db, kind=args.kind)
    (args.directory / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    for path in result['paths']:
        if abs(path['correlation']) > 0.1:
            print(path)
    print({k: result[k] for k in ['finite', 'silent', 'clipped', 'xruns']})
    if xruns or not result['finite'] or result['silent'] or result['clipped']:
        raise SystemExit('INVALID audio run; see report.json')


if __name__ == '__main__':
    main()
