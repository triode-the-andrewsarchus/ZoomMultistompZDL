"""Offline fault tests: never opens MIDI/audio ports."""
import unittest
from unittest.mock import Mock

import mido
import numpy as np
from file_session import crc32_tail, pack7
from backup import CheckedInput
from audio import analyze


class BackupTests(unittest.TestCase):
    def packet(self, body, length=None):
        n = len(body) if length is None else length
        return mido.Message('sysex', data=[0x52, 0, 0x6e, 0x64, 0x12, 0, n & 127, n >> 7]
                            + list(pack7(body)) + list(crc32_tail(body)))

    def test_crc_and_length_are_required(self):
        body = b'PTCF\x80\xff' * 20
        port = Mock()
        port.poll.return_value = self.packet(body)
        self.assertEqual(CheckedInput(port).receive(), port.poll.return_value)
        port.poll.return_value = self.packet(body, len(body) - 1)
        with self.assertRaises(RuntimeError):
            CheckedInput(port).receive()
        bad = list(self.packet(body).data)
        bad[-2] ^= 1
        port.poll.return_value = mido.Message('sysex', data=bad)
        with self.assertRaises(RuntimeError):
            CheckedInput(port).receive()


class AudioTests(unittest.TestCase):
    def test_known_delay_gain_and_silence(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 0.01, (2000, 2))
        x[1000:, 0] = 0
        x[:1000, 1] = 0
        y = np.zeros_like(x)
        y[137:] = x[:-137] * 0.5
        result = analyze(x, y, 48000)
        for channel in range(2):
            path = next(p for p in result['paths'] if p['send'] == channel and p['capture'] == channel)
            self.assertEqual(path['latency_samples'], 137)
            self.assertAlmostEqual(path['gain_db'], -6.0205999, places=5)
        self.assertTrue(analyze(x, np.zeros_like(x), 48000)['silent'])
        y[0, 0] = 1
        self.assertTrue(analyze(x, y, 48000)['clipped'])


if __name__ == '__main__':
    unittest.main()
