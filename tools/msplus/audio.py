#!/usr/bin/env python3
"""Explicit JACK/PipeWire send/return capture. No MIDI or interface mixer writes.

Discovery records every physical capture port, sending distinct probes to the
specified outputs only. Default peak is -50 dBFS. Connection names and xruns are
saved alongside WAVs; an xrun makes the run invalid. Outputs stop on exit.
"""
import argparse
import contextlib
import re
import subprocess
import json
import threading
import time
from pathlib import Path

import jack
import numpy as np
import soundfile as sf
from scipy import signal


def pipewire_quantum():
    text = subprocess.check_output(['pw-metadata', '-n', 'settings'], text=True)
    match = re.search(r"key:'clock.force-quantum' value:'(\d+)'", text)
    if not match:
        raise RuntimeError('Cannot read PipeWire forced quantum; refusing to change it')
    return int(match[1])


@contextlib.contextmanager
def temporary_quantum(frames=512):
    """Give Python callbacks headroom; restore the user's setting on exit."""
    previous = pipewire_quantum()
    command = ['pw-metadata', '-n', 'settings', '0', 'clock.force-quantum']
    try:
        subprocess.run(command + [str(frames)], check=True, stdout=subprocess.DEVNULL)
        if pipewire_quantum() != frames:
            raise RuntimeError('PipeWire did not apply the requested buffer size')
        yield
    finally:
        # Preserve an intervening user change instead of overwriting it.
        if pipewire_quantum() == frames:
            subprocess.run(command + [str(previous)], check=True, stdout=subprocess.DEVNULL)


def stimulus(rate, level_db, kind):
    amplitude = 10 ** (level_db / 20)
    n = int(rate * 6)
    result = np.zeros((n, 2), np.float32)
    if kind == 'silence':
        return result
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


class AudioRig:
    """One JACK client and fixed connections for an entire measurement session."""
    def __init__(self, sends, returns):
        self.sends = sends
        self.returns = physical_ports(sends, returns)
        self.client = jack.Client('zdl-hil', no_start_server=True)
        self.rate = self.client.samplerate
        self.blocksize = self.client.blocksize
        self.outputs = [self.client.outports.register(f'send_{i}') for i in range(2)]
        self.inputs = [self.client.inports.register(f'return_{i}') for i in range(len(self.returns))]
        self.test = None
        self.position = 0
        self.done = threading.Event()
        self.xruns = []
        self.client.set_process_callback(self.process)
        self.client.set_xrun_callback(self.on_xrun)

    def on_xrun(self, delay):
        if self.test is not None:
            self.xruns.append(float(delay))

    def process(self, frames):
        count = min(frames, len(self.test) - self.position) if self.test is not None else 0
        for ch, port in enumerate(self.outputs):
            buf = port.get_array()
            buf[:] = 0
            if count:
                buf[:count] = self.test[self.position:self.position + count, ch]
        if not count:
            return
        for ch, port in enumerate(self.inputs):
            self.recording[self.position:self.position + count, ch] = port.get_array()[:count]
        self.position += count
        if self.position == len(self.test):
            self.test = None
            self.done.set()

    def __enter__(self):
        self.client.activate()
        try:
            for out, dest in zip(self.outputs, self.sends):
                self.client.connect(out, dest)
            for src, inp in zip(self.returns, self.inputs):
                self.client.connect(src, inp)
            time.sleep(0.25)
            self.blocksize = self.client.blocksize
            return self
        except BaseException:
            self.client.close()
            raise

    def record(self, test):
        self.recording = np.zeros((len(test), len(self.inputs)), np.float32)
        self.xruns = []
        self.position = 0
        self.done.clear()
        self.test = test       # publish only after every capture field is ready
        if not self.done.wait(len(test) / self.rate + 5):
            self.test = None
            raise TimeoutError('JACK callback stalled')
        return self.recording, self.xruns

    def __exit__(self, *_):
        self.test = None
        self.client.deactivate()
        self.client.close()


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


def physical_ports(sends, returns=None):
    with jack.Client('zdl-discovery', no_start_server=True) as client:
        playback = {p.name for p in client.get_ports(is_audio=True, is_physical=True, is_input=True)}
        capture_ports = [p.name for p in client.get_ports(is_audio=True, is_physical=True, is_output=True)]
    chosen = returns or [p for p in capture_ports if 'AF16Rig' in p]
    if not set(sends) <= playback:
        raise ValueError('Requested sends are not physical playback ports')
    if not chosen or not set(chosen) <= set(capture_ports):
        raise ValueError('Requested returns are not physical capture ports')
    return chosen


def run_capture(directory, sends, returns=None, kind='probe', level_db=-50, rig=None):
    if not -80 <= level_db <= -20:
        raise ValueError('Level must be between -80 and -20 dBFS')
    chosen = rig.returns if rig is not None else physical_ports(sends, returns)
    directory.mkdir(parents=True, exist_ok=False)
    if rig is None:
        with AudioRig(sends, chosen) as opened:
            return _record_capture(directory, opened, kind, level_db)
    return _record_capture(directory, rig, kind, level_db)


def _record_capture(directory, rig, kind, level_db):
    rate, blocksize = rig.rate, rig.blocksize
    test = stimulus(rate, level_db, kind)
    recording, xruns = rig.record(test)
    sf.write(directory / 'send.wav', test, rate, subtype='FLOAT')
    sf.write(directory / 'return.wav', recording, rate, subtype='FLOAT')
    result = analyze(test, recording, rate)
    result.update(rate=rate, blocksize=blocksize, sends=rig.sends, returns=rig.returns, xruns=xruns,
                  level_db=level_db, kind=kind)
    (directory / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    if xruns or not result['finite'] or result['clipped']:
        raise RuntimeError('INVALID audio capture; see report.json')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory', type=Path)
    ap.add_argument('--send', nargs=2, required=True, help='Exact physical JACK port names')
    ap.add_argument('--return-ports', nargs='+', help='Exact physical capture ports; default: all AudioFuse ports')
    ap.add_argument('--level-db', type=float, default=-50)
    ap.add_argument('--kind', choices=['probe', 'tone', 'sweep', 'silence'], default='probe')
    args = ap.parse_args()
    result = run_capture(args.directory, args.send, args.return_ports, args.kind, args.level_db)
    for path in result['paths']:
        if abs(path['correlation']) > 0.1:
            print(path)
    print({k: result[k] for k in ['finite', 'silent', 'clipped', 'xruns']})
    if result['silent'] and args.kind != 'silence':
        raise SystemExit('INVALID audio run: silence; see report.json')


if __name__ == '__main__':
    main()
