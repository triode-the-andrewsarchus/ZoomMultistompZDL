"""Compile the real Plus kernels natively; exercise state/coeff/bus safety."""
import re
import unittest

import numpy as np
from scipy import signal

from native import Kernel, ROOT


class DSPTests(unittest.TestCase):
    def test_faults_fail_closed_and_stay_in_bounds(self):
        for name in ['gain', 'flower', 'klang', 'scorch', 'corrupt', 'howl', 'dustbox', 'calibrate', 'meminfo', 'genloss']:
            k = Kernel(name)
            canary = k.state[k.guard_word:].copy()
            k.state[k.guard_word] = 0
            self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
            k.state[k.guard_word] = k.guard
            for slot in [0] + list(range(5, 5 + len(k.manifest['params']))):
                original = k.coeff[slot]
                k.coeff[slot] = np.nan
                self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
                k.coeff[slot] = original
            result = k.block(np.full((16, 2), np.inf))
            self.assertTrue(np.isfinite(result).all())
            np.testing.assert_array_equal(canary, k.state[k.guard_word:])

    def test_memory_telemetry_is_disarmed_and_descriptor_read_only(self):
        k = Kernel('meminfo')
        k.instance[3] = 1  # Invalid pointer must never be accessed while disarmed.
        self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
        descriptor = np.array([0x12345678, 0x123c5678, 0x60000], np.uint32)
        original = descriptor.copy()
        k.instance[3] = descriptor.ctypes.data
        k.coeff[5] = 1
        audio = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(10000)])
        np.testing.assert_array_equal(descriptor, original)
        np.testing.assert_array_equal(k.state[1:4], original)
        self.assertLessEqual(np.max(abs(audio)), 0.000201)
        # First byte pair after the half-second preamble.
        segment = audio[24255:39690]
        freq = np.fft.rfftfreq(len(segment), 1 / 44100)
        for ch, byte in enumerate([0x78, 0x56]):
            measured = freq[np.argmax(abs(np.fft.rfft(segment[:, ch])))]
            self.assertLess(abs(measured - (400 + byte * 20)), 4)

    def test_genloss_bounded_ring_and_independent_delay_reference(self):
        k = Kernel('genloss', arena_bytes=16384)
        k.coeff[5:9] = [0, 1, 0, 1]
        rng = np.random.default_rng(53)
        samples = rng.normal(0, 0.01, (16000, 2))
        output = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
        x = samples.mean(axis=1) * 1.8
        driven = 1.5*x - 0.5*x**3
        delayed = np.zeros(len(x)); delayed[529:] = driven[:-529]
        hp = signal.lfilter([0.012], [1, -0.988], delayed)
        expected = signal.lfilter([0.53], [1, -0.47], delayed-hp) * 1.15
        self.assertLess(np.sqrt(np.mean((output[:, 0]-expected)**2)), 1e-6)
        np.testing.assert_allclose(output[:, 0], output[:, 1], atol=1e-8)
        np.testing.assert_array_equal(k.arena[:2], [0xcafef00d]*2)
        np.testing.assert_array_equal(k.arena[-2:], [0xcafef00d]*2)
        k.coeff[8] = 0
        np.testing.assert_allclose(k.block(samples[:16]), samples[:16].mean(axis=1)[:, None].repeat(2, axis=1), atol=1e-8)

    def test_genloss_rejects_inconsistent_or_small_grants_before_writing(self):
        for mode in ['small', 'mismatch', 'oversize']:
            k = Kernel('genloss', arena_bytes=16384)
            if mode == 'small':
                k.descriptor[1] = k.descriptor[0] + 64
                k.descriptor[2] = 64
            elif mode == 'mismatch':
                k.descriptor[2] += 4
            else:
                k.descriptor[1] = k.descriptor[0] + 705604
                k.descriptor[2] = 705604
            before = k.arena.copy()
            self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
            np.testing.assert_array_equal(k.arena, before)

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

    def test_klang_sidebands_and_extreme_state(self):
        k = Kernel('klang')
        k.coeff[5:8] = [0.2, 0, 1]
        t = np.arange(88208) / 44100
        samples = np.column_stack([0.1 * np.sin(2 * np.pi * 997 * t)] * 2)
        output = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
        freq = np.fft.rfftfreq(len(output), 1 / 44100)
        spectrum = abs(np.fft.rfft(output * np.hanning(len(output))[:, None], axis=0))
        for ch, carrier in enumerate([400.4, 400.4 * 1.006]):
            for expected in [997 - carrier, 997 + carrier]:
                nearby = np.abs(freq - expected) < 5
                measured = freq[nearby][np.argmax(spectrum[nearby, ch])]
                self.assertLess(abs(measured - expected), 1)
        k.coeff[5:8] = 1
        for _ in range(1000):
            output = k.block(np.full((16, 2), 0.1))
            self.assertTrue(np.isfinite(output).all())
            self.assertLess(np.max(abs(output)), 2)

    def test_resonator_and_synth_remain_bounded(self):
        rng = np.random.default_rng(12)
        for name in ['scorch', 'corrupt', 'howl', 'dustbox']:
            k = Kernel(name)
            k.coeff[5:5 + len(k.manifest['params'])] = 1
            samples = rng.normal(0, 0.1, (44160, 2))
            audio = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
            self.assertTrue(np.isfinite(audio).all())
            self.assertLessEqual(np.max(abs(audio)), 1.5)
            # Once excited, all three must remain finite through silence.
            for _ in range(15000):
                audio = k.block(np.zeros((16, 2)))
            self.assertTrue(np.isfinite(audio).all())
            self.assertLess(np.max(abs(audio)), 0.01)

    def test_scorch_matches_independent_filter_reference(self):
        k = Kernel('scorch')
        rng = np.random.default_rng(51)
        samples = rng.normal(0, 0.03, (16000, 2))
        k.coeff[5:7] = [0.22, 1]
        output = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
        mono = samples.mean(axis=1)
        hp = signal.lfilter([0.0135], [1, -(1 - 0.0135)], mono)
        def soft(x):
            v = np.clip(x, -1, 1)
            return 1.5 * v - 0.5 * v ** 3
        stage1 = soft((mono - hp) * (1 + 0.22 * 45) + 0.18) - soft(0.18)
        lp = signal.lfilter([0.575], [1, -(1 - 0.575)], stage1)
        nonlinear = soft(soft(lp * (1 + 0.22 * 6)) * 1.6)
        source = (ROOT / 'src/custom/scorch/scorch.c').read_text()
        sos = []
        for index in range(5):
            values = [float(re.search(r'#define SC_' + term + '_' + str(index) + r'\s+([-+0-9.eE]+)f', source)[1])
                      for term in ['B0', 'B1', 'B2', 'A1', 'A2']]
            sos.append(values[:3] + [1] + values[3:])
        expected = np.clip(signal.sosfilt(sos, nonlinear) * 0.55, -1, 1)
        self.assertLess(np.sqrt(np.mean((output[:, 0] - expected) ** 2)), 0.0003)
        np.testing.assert_allclose(output[:, 0], output[:, 1], atol=1e-7)

    def test_howl_matches_stable_two_pole_reference(self):
        k = Kernel('howl')
        k.coeff[5:8] = [0.35, 0.5, 1]
        impulse = np.zeros((16000, 2))
        impulse[0] = 0.001
        output = np.concatenate([k.block(b) for b in impulse.reshape(-1, 16, 2)])
        r = 1 - (3e-5 + 1.2e-3 * 0.5 ** 2)
        for ch, detune in enumerate([1, 1.012]):
            w = 2 * np.pi / 44100 * (80 + 0.35 * 1870) * detune
            a1, a2 = 2 * r * (1 - 0.5 * w * w), -r * r
            y = signal.lfilter([0.12], [1, -a1, -a2], impulse[:, ch])
            v = np.clip(y * 2.4, -1, 1)
            expected = (1.5 * v - 0.5 * v ** 3) * 0.42
            self.assertLess(np.sqrt(np.mean((output[:, ch] - expected) ** 2)), 0.00003)

    def test_calibration_probe_cannot_exceed_quiet_ceiling(self):
        k = Kernel('calibrate')
        k.coeff[5] = 1
        audio = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(1000)])
        self.assertLessEqual(np.max(abs(audio)), 0.001001)
        np.testing.assert_allclose(np.sqrt(np.mean(audio ** 2, axis=0)), 0.001 / np.sqrt(3), rtol=0.01)


if __name__ == '__main__':
    unittest.main()
