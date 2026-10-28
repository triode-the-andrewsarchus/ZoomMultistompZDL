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


class AuditionSafetyTests(unittest.TestCase):
    def test_forbidden_commands_cannot_reach_output(self):
        import io
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.log = io.StringIO()
        session.pedal = Mock()
        for command in [[0x52, 0, 0x6e, 0x5b], [0x52, 0, 0x6e, 0x28],
                        [0x52, 0, 0x6e, 0x01], [0x52, 0, 0x6e, 0x60, 0x24]]:
            with self.assertRaises(ValueError):
                session.transmit_sysex(command)
        session.pedal.outport.send.assert_not_called()

    def test_edit_failure_prevents_automatic_cleanup_edits(self):
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.protocol_ok = True
        session._edit_checked = Mock(side_effect=RuntimeError('bad reply'))
        with self.assertRaises(RuntimeError):
            session.edit(2, 50)
        self.assertFalse(session.protocol_ok)

    def test_known_notifications_drain_but_errors_stop(self):
        import io
        from audition import TempPatch
        session = TempPatch.__new__(TempPatch)
        session.log = io.StringIO()
        session.pedal = Mock()
        session.pedal.inport.poll.side_effect = [mido.Message('sysex', data=[0x52, 0, 0x6e, 0x64, 0x20, 1]), None]
        session.drain()
        session.pedal.inport.poll.side_effect = [mido.Message('sysex', data=[0x52, 0, 0x6e, 0, 1])]
        with self.assertRaises(RuntimeError):
            session.drain()


if __name__ == '__main__':
    unittest.main()
