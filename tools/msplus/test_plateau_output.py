"""Output-stage comparisons against unmodified pinned Plateau DSP equations."""
import ctypes
import json
import shutil
import subprocess
import unittest

import numpy as np
from native import ROOT


class PlateauOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dependency=ROOT/'build/msplus/plateau'
        pin=json.loads((ROOT/'tools/msplus/upstream.lock.json').read_text())['plateau']
        actual=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:raise RuntimeError('Wrong Plateau reference revision')
        subprocess.run(['git','-C',str(dependency),'diff','--exit-code','HEAD'],check=True)
        oracle=ROOT/'build/msplus/plateau-output-oracle';oracle.mkdir(exist_ok=True)
        shutil.copytree(dependency/'signalsmith',oracle/'signalsmith',dirs_exist_ok=True)
        firmware=(dependency/'PlateauTest.cpp').read_text()
        soft=firmware[firmware.index('struct ExponentialRelease'):firmware.index('DaisyVersio hw;')]
        (oracle/'softlimiter.hpp').write_text(soft)
        cls.functions=[];cls.libraries=[]
        for derived in (False,True):
            out=ROOT/'build/msplus'/('plateau-output-derived.so' if derived else 'plateau-output-original.so')
            subprocess.run(['c++','-shared','-fPIC','-O2','-std=c++14',
                            '-I'+str(ROOT/'src/msplus/plateau' if derived else oracle),
                            *(['-DPL_DERIVED'] if derived else []),
                            str(ROOT/'tools/msplus/plateau_output_oracle.cpp'),
                            '-o',str(out)],check=True)
            lib=ctypes.CDLL(str(out));cls.libraries.append(lib)
            fn=lib.plateau_soft_render
            fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p]
            cls.functions.append(fn)
            if derived:
                cls.output_fn=lib.plateau_output_render
                cls.output_fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_float,ctypes.c_float]

    def render(self,source,limit):
        source=np.ascontiguousarray(source,dtype=np.float32)
        limit=np.broadcast_to(np.float32(limit),source.shape).copy()
        rows=[]
        for fn in self.functions:
            out=np.zeros_like(source)
            fn(source.ctypes.data,out.ctypes.data,len(source),limit.ctypes.data)
            self.assertTrue(np.isfinite(out).all());rows.append(out)
        return rows

    def test_level_limit_and_stereo_isolation(self):
        n=64000;t=np.arange(n,dtype=np.float32)
        source=np.c_[2*np.sin(t*.031),np.zeros(n)].astype(np.float32)
        for level in (0,.5,1,2):
            for amount in (0,.5,1):
                with self.subTest(level=level,amount=amount):
                    out=np.zeros_like(source)
                    self.output_fn(source.ctypes.data,out.ctypes.data,n,level,amount)
                    original,_=self.render(source[:,0]*level,.25*(1-amount))
                    np.testing.assert_allclose(out[:,0],original,atol=3e-5,rtol=2e-4)
                    np.testing.assert_array_equal(out[:,1],0)
                    self.assertLess(np.max(abs(out)),.851)

    def test_output_under_address_and_undefined_sanitizers(self):
        output=ROOT/'build/msplus/plateau-output-sanitized'
        subprocess.run(['c++','-O1','-g','-std=c++14','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-DPL_DERIVED','-DPL_SANITIZE_MAIN',
                        '-I'+str(ROOT/'src/msplus/plateau'),
                        str(ROOT/'tools/msplus/plateau_output_oracle.cpp'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True)

    def test_exact_delay_and_unlimited_unity(self):
        source=np.random.default_rng(77).uniform(-.1,.1,32000).astype(np.float32)
        original,derived=self.render(source,.85)
        expected=np.r_[np.zeros(320),source[:-320]]
        np.testing.assert_array_equal(original,expected)
        np.testing.assert_allclose(derived,expected,atol=1e-7,rtol=0)

    def test_peak_hold_release_and_changing_limits(self):
        n=320000;t=np.arange(n,dtype=np.float32)
        source=(3*np.sin(t*.031)+.5*np.sin(t*.37)).astype(np.float32)
        source[40000:100000]=0;source[150000:200000]*=.01
        limits=np.repeat(np.array([.85,.1,.5,0,.85],np.float32),64000)
        original,derived=self.render(source,limits)
        np.testing.assert_allclose(derived,original,atol=3e-5,rtol=2e-4)
        self.assertLess(np.max(abs(derived)),.851)


if __name__=='__main__':unittest.main()
