"""Compile the real Plus kernels natively; exercise state/coeff/bus safety."""
import ctypes
import json
import re
import subprocess
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


class Kernel:
    def __init__(self, name):
        folder = ROOT / 'src/msplus' / name
        self.manifest = json.loads((folder / 'manifest.json').read_text())
        header = (folder / 'build/sh_params.h').read_text()
        symbol = re.search(r'#define SH_AUDIO_FN (\w+)', header)[1]
        so = ROOT / 'build/msplus' / f'{name}-host.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wno-unknown-pragmas',
                        '-I' + str(folder / 'build'), str(folder / self.manifest['kernel']),
                        '-o', str(so)], check=True)
        self.lib = ctypes.CDLL(str(so))
        self.fn = getattr(self.lib, symbol)
        self.fn.argtypes = [ctypes.POINTER(ctypes.c_void_p)] * 2
        self.coeff = np.zeros(16, np.float32)
        self.coeff[0] = 1
        for index, param in enumerate(self.manifest['params'], 5):
            self.coeff[index] = param['default'] / param['max']
        self.state = np.zeros(48, np.uint32)
        self.guard_word = int(re.search(r'#define SH_STATE_GUARD_WORD\s+(\d+)', header)[1])
        self.guard = int(re.search(r'#define SH_STATE_GUARD\s+(0x[0-9A-Fa-f]+)', header)[1], 16)
        self.state[self.guard_word] = self.guard
        self.bus = np.zeros(32, np.float32)
        self.instance = (ctypes.c_void_p * 3)(None, self.coeff.ctypes.data, self.state.ctypes.data)
        self.ctx = (ctypes.c_void_p * 2)(None, self.bus.ctypes.data)

    def block(self, samples):
        self.bus[:] = np.asarray(samples).T.reshape(32)
        self.fn(self.instance, self.ctx)
        return self.bus.reshape(2, 16).T.copy()


class DSPTests(unittest.TestCase):
    def test_faults_fail_closed_and_stay_in_bounds(self):
        for name in ['gain', 'flower']:
            k = Kernel(name)
            canary = k.state[k.guard_word:].copy()
            k.state[k.guard_word] = 0
            self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
            k.state[k.guard_word] = k.guard
            for slot in [0, 5]:
                original = k.coeff[slot]
                k.coeff[slot] = np.nan
                self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
                k.coeff[slot] = original
            result = k.block(np.full((16, 2), np.inf))
            self.assertTrue(np.isfinite(result).all())
            np.testing.assert_array_equal(canary, k.state[k.guard_word:])

    def test_gain_settling_bypass_and_channel_isolation(self):
        k = Kernel('gain')
        k.coeff[5] = 0.5
        sample = np.tile([0.2, -0.1], (16, 1))
        for _ in range(500):
            output = k.block(sample)
        np.testing.assert_allclose(output, sample * 0.5, atol=2e-6)
        k.coeff[0] = 0
        np.testing.assert_array_equal(k.block(sample), sample.astype(np.float32))

    def test_flower_matches_independent_sample_reference(self):
        k = Kernel('flower')
        k.coeff[5:7] = [0.3, 1]
        rng = np.random.default_rng(2)
        samples = rng.normal(0, 0.01, (44160, 2)).astype(np.float32)
        actual = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
        expected = np.zeros_like(samples)
        for ch, seed in enumerate([0x12345678, 0x9e3779b9]):
            low = band = 0.
            cut = target = 600.
            phase = ch * 0.5
            for i, value in enumerate(samples[:, ch]):
                phase += (0.5 + 0.3 * 13.5) / 44100
                if phase >= 1:
                    phase -= 1
                    seed ^= (seed << 13) & 0xffffffff
                    seed ^= seed >> 17
                    seed ^= (seed << 5) & 0xffffffff
                    target = 150 + (seed >> 9) / 8388608 * 2850
                cut += 0.05 * (target - cut)
                f = 2 * np.pi / 44100 * cut
                low += f * band
                band += f * (value - low - 0.18 * band)
                expected[i, ch] = np.clip(low + 0.9 * band, -2, 2)
        # Float phase accumulation moves random transitions by a few samples.
        self.assertLess(np.sqrt(np.mean((actual - expected) ** 2)), 0.002)
        k.coeff[0] = 0
        np.testing.assert_allclose(k.block(samples[:16]), samples[:16], atol=1e-8)


if __name__ == '__main__':
    unittest.main()
