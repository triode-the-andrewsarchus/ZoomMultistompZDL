"""Native host for the same C kernels built by the ZD2 pipeline (no hardware)."""
import ctypes
import json
import re
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MATU_PORTS = ('wavefold', 'dualshft', 'formant', 'eugate', 'dubsiren', 'sgnl',
              'scrub', 'griddly', 'synceq', 'breather', 'dirtbox', 'sweep')


class Kernel:
    def __init__(self, name, arena_bytes=0):
        folder = ROOT / 'src/msplus' / name
        self.manifest = json.loads((folder / 'manifest.json').read_text())
        header = (folder / 'build/sh_params.h').read_text()
        symbol = re.search(r'#define SH_AUDIO_FN (\w+)', header)[1]
        so = ROOT / 'build/msplus' / f'{name}-host.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-O2', '-Wno-unknown-pragmas',
                        '-I' + str(folder / 'build'), '-I' + str(ROOT / 'build/msplus/headers' / name), str(folder / self.manifest['kernel']),
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
        self.instance = (ctypes.c_void_p * 4)(None, self.coeff.ctypes.data, self.state.ctypes.data, None)
        self.ctx = (ctypes.c_void_p * 2)(None, self.bus.ctypes.data)
        if arena_bytes:
            self.arena = np.full(arena_bytes // 4 + 4, 0xcafef00d, np.uint32)
            base = self.arena.ctypes.data + 8
            self.descriptor = np.array([base, base + arena_bytes, arena_bytes], np.uintp)
            self.instance[3] = self.descriptor.ctypes.data


    def block(self, samples):
        self.bus[:] = np.asarray(samples).T.reshape(32)
        self.fn(self.instance, self.ctx)
        return self.bus.reshape(2, 16).T.copy()

