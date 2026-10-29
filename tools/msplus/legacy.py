"""Host-only reference: original pre-port C, with pointer-width/bookkeeping fixes.

The DSP math and eight-frame processing are unchanged. No MIDI or audio-device
access. This reference deliberately uses the original entry and parameter path.
"""
import ctypes
import json
import re
import subprocess
import sys

import numpy as np
from native import ROOT

BASE = '71f4582b18aba5da565e4e9abee920173706f73c'


class LegacyKernel:
    def __init__(self, name):
        manifest = json.loads((ROOT / 'src/msplus' / name / 'manifest.json').read_text())
        legacy = (ROOT / 'src/msplus' / name / manifest['legacy_manifest']).resolve() if 'legacy_manifest' in manifest else ROOT / 'src/custom' / name / 'manifest_pedal.json'
        source = legacy.parent / (legacy.parent.name + '.c')
        prefix = legacy.parent.name.upper()
        directory = ROOT / 'build/msplus/legacy-native' / name
        directory.mkdir(parents=True, exist_ok=True)
        sys.path.insert(0, str(ROOT / 'src/airwindows/common'))
        sys.path.insert(0, str(ROOT / 'build'))
        from manifest_params import write_param_header
        old_manifest = json.loads(legacy.read_text())
        write_param_header(old_manifest, directory / (legacy.parent.name + '_params.h'), prefix)
        text = subprocess.check_output(['git', 'show', BASE + ':' + str(source.relative_to(ROOT))], cwd=ROOT, text=True)
        text = re.sub(r'unsigned int\s*\*ctx', 'uintptr_t *ctx', text)
        text = text.replace('volatile unsigned int', 'volatile uintptr_t')
        text = text.replace('*magicDst = *magicSrc;', '')
        copied = directory / 'reference.c'
        copied.write_text(text)
        shared = directory / 'reference.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wno-unknown-pragmas',
                        '-D' + prefix + '_AUDIO_FUNC=LegacyDSP', '-I' + str(source.parent),
                        '-I' + str(directory), str(copied), '-o', str(shared)], check=True)
        self.lib = ctypes.CDLL(str(shared))
        self.fn = self.lib.LegacyDSP
        self.fn.argtypes = [ctypes.c_void_p]
        self.params = np.zeros(32, np.float32)
        self.params[0] = 1
        for i, p in enumerate(old_manifest['params'], 5):
            self.params[i] = p['default'] / p['max']
        self.arena = np.full(705600 // 4 + 4, 0xcafef00d, np.uint32)
        base = self.arena.ctypes.data + 8
        self.descriptor = np.array([base, base + 705600, 705600], np.uintp)
        self.bus = np.zeros(16, np.float32)
        self.magic = np.zeros(1, np.uint32)
        self.ctx = np.zeros(13, np.uintp)
        self.ctx[[1, 3, 5, 11, 12]] = [self.params.ctypes.data, self.descriptor.ctypes.data,
                                      self.bus.ctypes.data, self.magic.ctypes.data, self.magic.ctypes.data]

    def block(self, samples):
        self.bus[:] = np.asarray(samples).T.reshape(16)
        self.fn(self.ctx.ctypes.data)
        return self.bus.reshape(2, 8).T.copy()
