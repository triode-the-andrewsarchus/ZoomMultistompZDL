"""Plateau float adaptation against the pinned upstream double DSP core."""
import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import numpy as np
from native import ROOT


class PlateauCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dependency=ROOT/'build/msplus/plateau'
        pin=json.loads((ROOT/'tools/msplus/upstream.lock.json').read_text())['plateau']
        actual=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:raise RuntimeError('Wrong Plateau reference revision')
        subprocess.run(['git','-C',str(dependency),'diff','--exit-code','HEAD'],check=True)
        oracle=ROOT/'build/msplus/plateau-core-oracle';oracle.mkdir(exist_ok=True)
        for path in ['Dattorro.cpp','Dattorro.hpp','dsp/delays/AllpassFilter.hpp',
                     'dsp/delays/InterpDelay.hpp','dsp/delays/InterpDelay.cpp',
                     'dsp/filters/OnePoleFilters.hpp','dsp/modulation/LFO.hpp','utilities/Utilities.hpp']:
            dest=oracle/path;dest.parent.mkdir(parents=True,exist_ok=True)
            text=(dependency/path).read_text()
            if path.startswith('dsp/delays/InterpDelay.'):
                text=text.replace('[144000]','[192010]')
            dest.write_text(text)
        (oracle/'daisy_versio.h').write_text('#define DSY_SDRAM_BSS\n')
        (oracle/'daisysp.h').write_text('')
        cls.libraries=[];cls.functions=[]
        for variant in ("original","derived","explicit"):
            derived=variant!="original"
            output=ROOT/'build/msplus'/('plateau-'+variant+'.so')
            include=ROOT/'src/msplus/plateau' if derived else oracle
            subprocess.run(['c++','-shared','-fPIC','-O2','-std=c++14','-I'+str(include),
                            *(['-DPL_DERIVED'] if derived else []),
                            *(['-DPLATEAU_EXPLICIT_INIT'] if variant=='explicit' else []),
                            str(ROOT/'tools/msplus/plateau_oracle.cpp'),
                            *([] if derived else [str(oracle/'Dattorro.cpp'),str(oracle/'dsp/delays/InterpDelay.cpp')]),
                            '-o',str(output)],check=True)
            lib=ctypes.CDLL(str(output));cls.libraries.append(lib)
            fn=lib.plateau_render
            fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p]
            cls.functions.append(fn)

    def render_pair(self,source,parameters):
        source=np.ascontiguousarray(source,dtype=np.float32)
        parameters=np.asarray(parameters,dtype=np.float32)
        rows=[]
        for fn in self.functions:
            out=np.zeros_like(source)
            result=fn(source.ctypes.data,out.ctypes.data,len(source),parameters.ctypes.data)
            self.assertGreater(result,0)
            self.assertTrue(np.isfinite(out).all())
            rows.append(out)
        return rows

    def test_impulse_core_matches_original_without_modulation(self):
        source=np.zeros((192000,2),np.float32);source[0,0]=.01
        for size,pre,decay in [(1.0075,0,.877465),(.01,.05,.5),(4,.5,.95)]:
            with self.subTest(size=size,predelay=pre):
                original,derived,explicit=self.render_pair(source,[size,pre,decay,1,0,.5,1,0,10,0,10])
                np.testing.assert_allclose(explicit,derived,atol=1e-7,rtol=1e-5)
                residual=np.linalg.norm(derived-original)/np.linalg.norm(original)
                self.assertLess(residual,.005)
                self.assertGreater(np.linalg.norm(derived),.001)

    def test_modulated_filtered_core_matches_upstream_energy(self):
        source=np.random.default_rng(33).normal(0,.001,(96000,2)).astype(np.float32)
        for size,depth,shape,diffusion in [(1,.5,.5,1),(4,16,.001,.7),(.01,16,.999,0)]:
            with self.subTest(size=size,depth=depth):
                original,derived,explicit=self.render_pair(source,[size,.1,.8,10,depth,shape,diffusion,2,8,1,9])
                np.testing.assert_allclose(explicit,derived,atol=1e-7,rtol=1e-5)
                # Float LFO accumulation gradually changes modulation phase;
                # compare energy per 100 ms window as well as a broad bound.
                a=np.sqrt(np.mean(original.reshape(-1,3200,2)**2,axis=1))
                b=np.sqrt(np.mean(derived.reshape(-1,3200,2)**2,axis=1))
                valid=a>1e-7
                self.assertLess(np.max(abs(20*np.log10(b[valid]/a[valid]))),.5)
                self.assertLess(np.max(abs(derived)),.05)


if __name__=='__main__':unittest.main()
