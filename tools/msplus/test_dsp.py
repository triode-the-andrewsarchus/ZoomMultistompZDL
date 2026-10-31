"""Compile the real Plus kernels natively; exercise state/coeff/bus safety."""
import re
from itertools import product
import unittest

import numpy as np
from scipy import signal

from native import Kernel, ROOT, MATU_PORTS


class DSPTests(unittest.TestCase):
    def test_wavefold_live_control_changes_stay_bounded(self):
        kernel=Kernel('wavefold',arena_bytes=705600)
        t=np.arange(88208)/44100
        source=np.column_stack([np.zeros(len(t)),.01*np.sin(2*np.pi*997*t)])
        peaks=[]
        for index,block in enumerate(source.reshape(-1,16,2)):
            if index%64==0:
                mode=index//64
                kernel.coeff[5:12]=[(mode%5)/4,(mode%3)/2,(mode%3)/2,1,.5,1,(mode%5)/4]
            out=kernel.block(block)
            self.assertTrue(np.isfinite(out).all())
            peaks.append(float(np.max(abs(out))))
        self.assertLess(max(peaks),.3)
        self.assertGreater(np.mean(peaks[-100:]),.001)
        np.testing.assert_array_equal(kernel.arena[:2],[0xcafef00d]*2)
        np.testing.assert_array_equal(kernel.arena[-2:],[0xcafef00d]*2)

    def test_wavefold_oversampling_reduces_alias_energy(self):
        kernel=Kernel('wavefold',arena_bytes=705600)
        kernel.coeff[5:11]=[.7,.5,.5,1,.5,1]
        t=np.arange(44160)/44100
        source=np.column_stack([np.zeros(len(t)),.0025*np.sin(2*np.pi*3100*t)])
        oversampled=np.concatenate([kernel.block(b) for b in source.reshape(-1,16,2)])[-22050:,1]
        plain=source[-22050:,1]*(2+126*.7**2)
        for _ in range(5):
            plain=np.sin(np.pi/2*plain*(.6366197724+2.1633802276*.7))
        frequencies=np.fft.rfftfreq(len(plain),1/44100)
        wanted=np.zeros(len(frequencies),bool)
        for harmonic in range(1,8):
            wanted |= abs(frequencies-3100*harmonic)<8
        ratios=[]
        for audio in (oversampled,plain):
            power=abs(np.fft.rfft(audio))**2
            power[0]=0
            ratios.append(10*np.log10(power[~wanted].sum()/power.sum()))
        self.assertLess(ratios[0]-ratios[1],-8)

    def test_wavefold_all_symmetry_values_and_voices_at_quiet_levels(self):
        kernel = Kernel('wavefold', arena_bytes=705600)
        phase = 2*np.pi*1000*np.arange(26464)/44100
        source = np.column_stack([np.zeros(len(phase)), np.sin(phase)])
        for amplitude in (.0008, .0025):
            for drive in (.4, 1):
                for voice in (0, .5, 1):
                    for symmetry in range(101):
                        kernel.state[:] = 0
                        kernel.state[kernel.guard_word] = kernel.guard
                        kernel.coeff[5:11] = [drive, symmetry/100, voice, 1, .5, 1]
                        out = np.concatenate([kernel.block(b*amplitude) for b in source.reshape(-1,16,2)])
                        y = out[-8820:,1]
                        fundamental = 2*abs(np.mean(y*np.exp(-1j*phase[-8820:])))
                        rms = np.sqrt(np.mean(y*y))
                        thd = np.sqrt(max(2*rms*rms-fundamental*fundamental, 0))/max(fundamental,1e-12)
                        with self.subTest(amplitude=amplitude, drive=drive, voice=voice, symmetry=symmetry):
                            self.assertGreater(thd, .01)
                            self.assertGreater(rms, amplitude*.2)
                            self.assertLess(rms, amplitude)
                            self.assertTrue(np.isfinite(kernel.arena[2:-2].view(np.float32)).all())

    def test_wavefold_voices_filter_before_folding_and_blend_clean_independently(self):
        phase = np.arange(44160)/44100
        source = np.column_stack([np.zeros(len(phase)), .0008*(np.sin(2*np.pi*200*phase)+np.sin(2*np.pi*4000*phase))])
        outputs = []
        for voice in (0,.5,1):
            kernel = Kernel('wavefold', arena_bytes=705600)
            kernel.coeff[5:11] = [0,.5,voice,1,.5,1]
            outputs.append(np.concatenate([kernel.block(b) for b in source.reshape(-1,16,2)])[:,1])
        low, full, blend = outputs
        delayed = np.pad(source[:-12,1], (12,0))
        np.testing.assert_allclose(blend, .55*full+.45*delayed, atol=2e-9)
        ratios = []
        for output in (low,full):
            segment = output[-22050:]
            levels = [abs(np.mean(segment*np.exp(-2j*np.pi*f*phase[-22050:]))) for f in (200,4000)]
            ratios.append(levels[1]/levels[0])
        self.assertLess(ratios[0]/ratios[1], .15)
        kernel = Kernel('wavefold', arena_bytes=705600)
        kernel.coeff[10] = 0  # Overall Mix remains independent of VOICE.
        actual = np.concatenate([kernel.block(b) for b in source.reshape(-1,16,2)])[:,1]
        np.testing.assert_allclose(actual, delayed, atol=1e-10)

    def test_wavefold_each_stage_count_matches_independent_sine_reference(self):
        import ctypes
        import subprocess
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'probe.c'; library=Path(tmp)/'probe.so'
            source.write_text('#include "'+str(ROOT/'src/msplus/wavefold/wavefold.c')+'"\n'
                              'float probe(float x,float gain,float bias,int stages){return wf_cascade(x,gain,bias,stages);}')
            subprocess.run(['cc','-shared','-fPIC','-O2','-I'+str(ROOT/'src/msplus/wavefold/build'),str(source),'-o',str(library)],check=True)
            lib=ctypes.CDLL(str(library));lib.probe.argtypes=[ctypes.c_float]*3+[ctypes.c_int];lib.probe.restype=ctypes.c_float
            x=np.linspace(-2,2,4001).astype(np.float32)
            for stages, gain, bias in product(range(1,6), (.6366197724,1.5,2.8), (-.5,0,.5)):
                expected=x.astype(float)
                for stage in range(stages):
                    sign=1 if stage%2==0 else -1
                    expected=np.sin(np.pi/2*(expected*np.float32(gain)+sign*bias))-sign*np.sin(np.pi/2*bias)
                actual=np.array([lib.probe(float(v),gain,bias,stages) for v in x])
                with self.subTest(stages=stages,gain=gain,bias=bias):
                    np.testing.assert_allclose(actual,expected,atol=.0003)
            five=np.array([lib.probe(float(v),2.8,0,5) for v in x])
            one=np.array([lib.probe(float(v),2.8,0,1) for v in x])
            self.assertGreater(np.sqrt(np.mean((five-one)**2)),.4)

    def test_wavefold_stage_selector_changes_audio_and_stays_silent_without_input(self):
        phase=np.arange(26464)/44100
        source=np.column_stack([np.zeros(len(phase)),.0025*np.sin(2*np.pi*997*phase)])
        outputs=[]
        kernel=Kernel('wavefold',arena_bytes=705600)
        self.assertEqual(kernel.manifest['params'][-1]['values'],['1','2','3','4','5'])
        for stages, voice in product(range(5), (0,.5,1)):
            kernel.state[:]=0;kernel.state[kernel.guard_word]=kernel.guard
            kernel.coeff[5:12]=[.7,.5,voice,1,.5,1,stages/4]
            for _ in range(10):
                np.testing.assert_array_equal(kernel.block(np.zeros((16,2))),0)
            out=np.concatenate([kernel.block(b) for b in source.reshape(-1,16,2)])[-8820:,1]
            self.assertGreater(np.sqrt(np.mean(out*out)),.0002)
            self.assertTrue(np.isfinite(kernel.arena[2:-2].view(np.float32)).all())
            outputs.append(out)
        outputs=outputs[1::3]  # FULL voice for each successive stage count.
        for a,b in zip(outputs,outputs[1:]):
            self.assertGreater(np.sqrt(np.mean((a-b)**2)),.0003)

    def test_packed_matujuice_controls_match_raw_state_audio_exactly(self):
        rng = np.random.default_rng(301)
        source = rng.normal(0, .01, (16384, 2)).astype(np.float32)
        for name in set(MATU_PORTS) - {'scrub', 'griddly'}:
            with self.subTest(port=name):
                packed = Kernel(name, arena_bytes=705600)
                raw = Kernel(name, arena_bytes=705600, raw_state=True)
                for setting in ('default', 'maximum', 'bypass'):
                    if setting == 'maximum':
                        packed.coeff[5:5+len(packed.manifest['params'])] = 1
                        raw.coeff[:] = packed.coeff
                    elif setting == 'bypass':
                        packed.coeff[0] = raw.coeff[0] = 0
                    for block in source.reshape(-1, 16, 2):
                        np.testing.assert_array_equal(packed.block(block), raw.block(block))
                    self.assertTrue(np.isfinite(packed.arena[2:-2].view(np.float32)).all())
                np.testing.assert_array_equal(packed.arena[:2], [0xcafef00d]*2)
                np.testing.assert_array_equal(packed.arena[-2:], [0xcafef00d]*2)

    def test_arena_header_roundtrip_preserves_every_bit_and_leaves_finite_storage(self):
        import ctypes
        import subprocess
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'header.c'
            library = Path(tmp) / 'header.so'
            source.write_text('#include <stdint.h>\n#include "' + str(ROOT / 'src/msplus/common/arena_state.h')
                              + '"\n#include "' + str(ROOT / 'src/msplus/common/pcm15.h')
                              + '"\nvoid pack(uintptr_t a,uintptr_t b,unsigned n){mp_pack_header(a,b,n);}\n'
                              'void unpack(uintptr_t a,uintptr_t b,unsigned n){mp_unpack_header(a,b,n);}\n'
                              'void put(short *p,int i,int v){mp_pcm15_write(p,i,v);}\n'
                              'int get(const short *p,int i){return mp_pcm15_read(p,i);}\n')
            subprocess.run(['cc', '-shared', '-fPIC', '-O2', str(source), '-o', str(library)], check=True)
            lib = ctypes.CDLL(str(library))
            for fn in (lib.pack, lib.unpack):
                fn.argtypes = [ctypes.c_size_t, ctypes.c_size_t, ctypes.c_uint]
            rng = np.random.default_rng(777)
            original = np.concatenate([np.array([0, 0xffffffff, 0x7f800000, 0xff800000,
                                                 0x7fc12345, 0x80000000], np.uint32),
                                       rng.integers(0, 2**32, 1024, dtype=np.uint32)])
            raw = np.pad(original, 1, constant_values=0xcafef00d)
            saved = np.full(2*len(original)+2, 0xcafef00d, np.uint32)
            lib.pack(raw.ctypes.data+4, saved.ctypes.data+4, original.nbytes)
            self.assertTrue((raw[1:-1] == 0).all())
            self.assertTrue(np.isfinite(saved[1:-1].view(np.float32)).all())
            self.assertLess(float(np.max(abs(saved[1:-1].view(np.float32)))), 1e-35)
            lib.unpack(raw.ctypes.data+4, saved.ctypes.data+4, original.nbytes)
            np.testing.assert_array_equal(raw[1:-1], original)
            np.testing.assert_array_equal(raw[[0, -1]], [0xcafef00d]*2)
            np.testing.assert_array_equal(saved[[0, -1]], [0xcafef00d]*2)
            lib.put.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            lib.get.argtypes = [ctypes.c_void_p, ctypes.c_int]
            pcm = np.zeros(32770, np.uint32)
            pcm[[0, -1]] = 0xcafef00d
            address = pcm.ctypes.data + 4
            values = np.arange(-32767, 32768)
            for index, value in enumerate(values):
                lib.put(address, index, int(value))
            decoded = np.array([lib.get(address, i) for i in range(len(values))])
            self.assertLessEqual(np.max(abs(decoded-values)), 1)
            self.assertEqual(lib.get(address, len(values)), 0, 'Writing must preserve the paired neighbour')
            self.assertTrue(np.isfinite(pcm[1:-1].view(np.float32)).all())
            self.assertLess(np.max(abs(pcm[1:-1].view(np.float32))), 1.1e-19)
            np.testing.assert_array_equal(pcm[[0, -1]], [0xcafef00d]*2)

    def test_scrub_position_selects_distinct_held_history_across_its_range(self):
        kernel = Kernel('scrub', arena_bytes=705600)
        knobs = {p['name']: (i, p['max']) for i, p in enumerate(kernel.manifest['params'], 5)}
        for name, value in {'Mix': 100, 'Glide': 0, 'Rec': 0, 'Dir': 0, 'Spray': 0}.items():
            index, maximum = knobs[name]
            kernel.coeff[index] = value / maximum
        zero = np.zeros((16, 2))
        for _ in range(4096):
            kernel.block(zero)
        rate = 44100
        t = np.arange(8 * rate) / rate
        frequency = 200 * (1 + np.floor(t))
        source = np.column_stack([np.zeros(len(t)), .1 * np.sin(2*np.pi*frequency*t)])
        for block in source.reshape(-1, 16, 2):
            kernel.block(block)
        kernel.coeff[knobs['Rec'][0]] = 1 / knobs['Rec'][1]
        measured = []
        for position, expected in zip((50, 150, 250, 350, 450, 550), range(600, 1800, 200)):
            kernel.coeff[knobs['Pos'][0]] = position / knobs['Pos'][1]
            held = np.concatenate([kernel.block(zero) for _ in range(1024)])[-8192:, 0]
            self.assertGreater(np.sqrt(np.mean(held**2)), .005)
            freq = np.fft.rfftfreq(len(held), 1/rate)
            peak = freq[np.argmax(abs(np.fft.rfft(held * np.hanning(len(held)))))]
            measured.append(peak)
            self.assertLess(abs(peak-expected), 20, (position, peak, expected))
        self.assertGreater(min(np.diff(measured)), 150)
        np.testing.assert_array_equal(kernel.arena[:2], [0xcafef00d]*2)
        np.testing.assert_array_equal(kernel.arena[-2:], [0xcafef00d]*2)

    def test_pcm_history_ports_keep_full_buffers_and_bound_clean_wet_reference_error(self):
        t = np.arange(65536)/44100
        source = np.column_stack([np.zeros(len(t)), .1*np.sin(2*np.pi*997*t)])
        for name in ('scrub', 'griddly'):
            with self.subTest(port=name):
                packed = Kernel(name, arena_bytes=705600)
                raw = Kernel(name, arena_bytes=705600, raw_state=True)
                edits = {'Mix': 100, 'Pos': 599, 'Glide': 0} if name == 'scrub' else {
                    'Mix': 100, 'Time': 1, 'Fdbk': 0, 'Char': 0}
                for i, param in enumerate(packed.manifest['params'], 5):
                    if param['name'] in edits:
                        packed.coeff[i] = raw.coeff[i] = edits[param['name']]/param['max']
                for _ in range(4096):
                    packed.block(np.zeros((16, 2)))
                    raw.block(np.zeros((16, 2)))
                actual = np.concatenate([packed.block(b) for b in source.reshape(-1, 16, 2)])
                expected = np.concatenate([raw.block(b) for b in source.reshape(-1, 16, 2)])
                self.assertGreater(np.max(abs(actual)), .01)
                # Both legacy cores use Q14: one stored PCM count is 1/16384.
                # Interpolation/windowing stays below two such counts here.
                self.assertLess(np.max(abs(actual-expected)), 2/16384)
                self.assertTrue(np.isfinite(packed.arena[2:-2].view(np.float32)).all())
                np.testing.assert_array_equal(packed.arena[:2], [0xcafef00d]*2)
                np.testing.assert_array_equal(packed.arena[-2:], [0xcafef00d]*2)

    def test_synceq_packed_state_survives_callbacks_and_instance_reinitialization(self):
        k = Kernel('synceq', arena_bytes=705600)
        source = np.tile([.02, .01], (16, 1))
        for _ in range(32):
            np.testing.assert_allclose(k.block(source), .01, atol=1e-8)
            self.assertTrue(np.isfinite(k.arena[2:-2].view(np.float32)).all())
            self.assertEqual(k.arena[2], 0)  # Raw magic is never left in the audio arena.
        k.coeff[6] = 1  # Low +12 dB, so the control state really changes.
        for _ in range(32):
            k.block(source)
        # Host _init clears small state when reinstantiating, while the same
        # arena address can be reused. Old encoded knobs must not survive it.
        k.state[:k.guard_word] = 0
        k.coeff[6] = .5
        for _ in range(8):
            np.testing.assert_allclose(k.block(source), .01, atol=1e-8)
        np.testing.assert_array_equal(k.arena[:2], [0xcafef00d]*2)
        np.testing.assert_array_equal(k.arena[-2:], [0xcafef00d]*2)

    def test_faults_fail_closed_and_stay_in_bounds(self):
        for name in ['gain', 'flower', 'klang', 'scorch', 'corrupt', 'howl', 'dustbox', 'calibrate', 'linearity', 'meminfo', 'genloss']:
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

    def test_original_rng_state_never_remains_as_nonfinite_audio_memory(self):
        for name in ('genloss', 'mangle'):
            with self.subTest(port=name):
                kernel = Kernel(name, arena_bytes=705600)
                for _ in range(4096):
                    output = kernel.block(np.full((16, 2), .01))
                    self.assertTrue(np.isfinite(output).all())
                    self.assertTrue(np.isfinite(kernel.arena[2:18].view(np.float32)).all())
                self.assertNotEqual(kernel.state[1], 0, 'RNG sequence must remain live in small state')

    def test_buffered_ports_bounds_parameter_faults_and_extremes(self):
        rng = np.random.default_rng(84)
        ports = ['microloom', 'shatter', 'arrakis', 'taffy', 'dissolve', 'mangle',
                 'rooms', 'hydra', 'spiral', 'stasis', 'rewire', 'gyre', 'galactic', 'spool', 'oxide']
        for name in ports:
            with self.subTest(port=name):
                k = Kernel(name, arena_bytes=705600)
                for _ in range(1024):
                    k.block(np.zeros((16, 2)))
                for slot in [0] + list(range(5, 5+len(k.manifest['params']))):
                    old = k.coeff[slot]; k.coeff[slot] = np.nan
                    before = k.arena.copy()
                    self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
                    np.testing.assert_array_equal(k.arena, before)
                    k.coeff[slot] = old
                samples = rng.normal(0, 0.01, (44160, 2))
                output = np.concatenate([k.block(b) for b in samples.reshape(-1, 16, 2)])
                self.assertTrue(np.isfinite(output).all())
                self.assertGreater(np.max(abs(output)), 1e-5)
                k.coeff[5:5+len(k.manifest['params'])] = 1
                for _ in range(2048):
                    self.assertTrue(np.isfinite(k.block(np.zeros((16, 2)))).all())
                np.testing.assert_array_equal(k.arena[:2], [0xcafef00d]*2)
                np.testing.assert_array_equal(k.arena[-2:], [0xcafef00d]*2)
                self.assertTrue(np.isfinite(k.block(np.full((16, 2), np.inf))).all())

    def test_buffered_math_matches_original_eight_frame_sources(self):
        from legacy import LegacyKernel
        rng = np.random.default_rng(71)
        names = ['genloss', 'microloom', 'shatter', 'arrakis', 'taffy', 'dissolve',
                 'mangle', 'rooms', 'hydra', 'spiral', 'stasis', 'rewire', 'gyre',
                 'galactic', 'spool', 'oxide']
        for name in names:
            with self.subTest(port=name):
                current = Kernel(name, arena_bytes=705600)
                old = LegacyKernel(name)
                for _ in range(4096):
                    current.block(np.zeros((16, 2)))
                # Align initialized histories before excitation; lazy-clear time
                # changes with callback geometry, while the sample math does not.
                old.arena[:] = current.arena
                # Logical state is equal although the Plus keeps these raw
                # integers outside memory that a factory delay reads as audio.
                if name in ('genloss', 'mangle'):
                    offset = 9 if name == 'genloss' else 11
                    old.arena[2 + offset] = current.state[1]
                old.params[5:5+len(current.manifest['params'])] = current.coeff[5:5+len(current.manifest['params'])]
                samples = rng.normal(0, 0.003, (16000, 2))
                actual = np.concatenate([current.block(b) for b in samples.reshape(-1, 16, 2)])
                expected = np.concatenate([old.block(b) for b in samples.reshape(-1, 8, 2)])
                error = np.sqrt(np.mean((actual-expected)**2))
                self.assertLess(error, 2e-6, f'{name}: RMS error {error}')

    def test_stasis_capture_remains_audible_while_bypassed(self):
        k = Kernel('stasis', arena_bytes=705600)
        k.coeff[0] = 0
        k.coeff[5] = 1
        k.coeff[9] = 1
        k.coeff[10] = 0.5  # Capture=1: release/live, even while bypassed.
        t = np.arange(88208)/44100
        source = np.column_stack([np.sin(2*np.pi*997*t)]*2)*0.01
        for b in source.reshape(-1, 16, 2):
            k.block(b)
        k.coeff[10] = 1  # Capture=2: hold independently of the bypass switch.
        held = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(4096)])
        self.assertGreater(np.sqrt(np.mean(held[-16000:]**2)), 0.001)
        k.coeff[10] = 0.5
        released = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(4096)])
        self.assertLess(np.sqrt(np.mean(released[-16000:]**2)), 1e-7)

    def test_matujuice_guards_canaries_and_active_dsp(self):
        t = np.arange(88208)/44100
        sample = np.column_stack([np.sin(2*np.pi*1499*t), np.sin(2*np.pi*997*t)])*0.01
        for name in MATU_PORTS:
            with self.subTest(port=name):
                k = Kernel(name, arena_bytes=705600)
                for _ in range(2048):
                    k.block(np.zeros((16, 2)))
                for slot in [0] + list(range(5, 5+len(k.manifest['params']))):
                    before = k.arena.copy(); value = k.coeff[slot]
                    k.coeff[slot] = np.nan
                    self.assertTrue((k.block(np.ones((16, 2))) == 0).all())
                    np.testing.assert_array_equal(k.arena, before)
                    k.coeff[slot] = value
                out = np.concatenate([k.block(b) for b in sample.reshape(-1, 16, 2)])
                self.assertTrue(np.isfinite(out).all())
                self.assertGreater(np.max(abs(out)), 1e-6)
                k.coeff[5:5+len(k.manifest['params'])] = 1
                for _ in range(512):
                    self.assertTrue(np.isfinite(k.block(np.zeros((16, 2)))).all())
                np.testing.assert_array_equal(k.arena[:2], [0xcafef00d]*2)
                np.testing.assert_array_equal(k.arena[-2:], [0xcafef00d]*2)
                self.assertTrue(np.isfinite(k.block(np.full((16, 2), np.inf))).all())

    def test_matujuice_left_input_and_grid_delay_bypass_tail(self):
        k = Kernel('wavefold', arena_bytes=705600)
        k.coeff[10] = 0  # Mix=0 is mono-left, aligned to the 12-sample FIR delay.
        source = np.tile([0.02, 0.01], (16, 1))
        delayed = k.block(source)
        np.testing.assert_array_equal(delayed[:12], 0)
        np.testing.assert_allclose(delayed[12:], .01, atol=1e-8)
        k.coeff[0] = 0
        np.testing.assert_allclose(k.block(source), source, atol=1e-8)
        k = Kernel('griddly', arena_bytes=705600)
        k.coeff[6] = 80/113
        k.coeff[11] = 1
        for _ in range(1024):
            k.block(np.zeros((16, 2)))
        t = np.arange(88208)/44100
        source = np.column_stack([np.zeros(len(t)), np.sin(2*np.pi*997*t)])*0.01
        for b in source.reshape(-1, 16, 2):
            k.block(b)
        k.coeff[0] = 0
        tail = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(2048)])
        self.assertGreater(np.sqrt(np.mean(tail**2)), 1e-4)
        k.coeff[13] = 0  # Tail OFF must then mute the delayed layer.
        muted = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(2048)])
        self.assertLess(np.sqrt(np.mean(muted[-16000:]**2)), 1e-7)

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

    def test_linearity_probe_starts_silent_and_respects_stepped_ceiling(self):
        k = Kernel('linearity')
        self.assertTrue((k.block(np.zeros((16, 2))) == 0).all())
        for level in (1, 25, 100, 0):
            k.coeff[5] = level/100
            audio = np.concatenate([k.block(np.zeros((16, 2))) for _ in range(1000)])
            peak = .55 * level/100
            self.assertLessEqual(np.max(abs(audio)), peak + 1e-7)
            np.testing.assert_allclose(np.sqrt(np.mean(audio**2, axis=0)), peak/np.sqrt(3), rtol=.01)


if __name__ == '__main__':
    unittest.main()
