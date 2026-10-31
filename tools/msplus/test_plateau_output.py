"""Output-stage comparisons against unmodified pinned Plateau DSP equations."""
import ctypes
import json
import re
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
        shutil.copytree(dependency/'src',oracle/'src',dirs_exist_ok=True)
        signal=(dependency/'src/dsp/signal.cpp').read_text()
        selected=signal[:signal.index('bool PositiveZeroCrossing::next')]
        selected+=signal[signal.index('void SlewLimiter::setParams'):signal.index('void ShapedSlewLimiter::setParams')]
        selected+=signal[signal.index('const float Saturator::limit'):signal.index('const float NoiseGate::maxEffectiveRatio')]
        utility=(dependency/'src/dsp/filters/utility.cpp').read_text()
        selected+='\n#include "filters/utility.hpp"\n'+utility[utility.index('float DCBlocker::next'):utility.index('float PureRootMeanSquare::next')]
        table=(dependency/'src/dsp/table.cpp').read_text()
        selected+=table[table.index('void Table::generate'):table.index('void SineTable::_generate')]
        (oracle/'lmtr_reference.cpp').write_text(selected)
        helpers=firmware[firmware.index('inline void saturation'):firmware.index('struct KnobOnePoleFilter')]
        gain=firmware[firmware.index('double modifier ='):firmware.index('struct PopFilter')]
        gain=re.sub(r'        if\(gainModeLedTimer <.*?\n        }\n','',gain,flags=re.S)
        (oracle/'gaincontrol.hpp').write_text('\n'.join([
            'using namespace bogaudio;', 'Lmtr limiter;',
            'LimiterAttackHoldRelease softerLimiterLeft,softerLimiterRight;',
            'double outputAmplification=0;int gainMode=0;',helpers,gain]))
        cls.functions=[];cls.libraries=[];cls.mode_functions=[]
        for derived in (False,True):
            out=ROOT/'build/msplus'/('plateau-output-derived.so' if derived else 'plateau-output-original.so')
            subprocess.run(['c++','-shared','-fPIC','-O2','-std=c++14',
                            '-I'+str(ROOT/'src/msplus/plateau' if derived else oracle),
                            *(['-DPL_DERIVED'] if derived else []),
                            str(ROOT/'tools/msplus/plateau_output_oracle.cpp'),
                            *([] if derived else [str(oracle/'lmtr_reference.cpp'),str(oracle/'src/Lmtr.cpp'),
                                                  '-I'+str(oracle/'src/dsp')]),'-o',str(out)],check=True)
            lib=ctypes.CDLL(str(out));cls.libraries.append(lib)
            fn=lib.plateau_soft_render
            fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p]
            cls.functions.append(fn)
            fn=lib.plateau_modes_render
            fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_uint,ctypes.c_float]
            cls.mode_functions.append(fn)

    def render(self,source,limit):
        source=np.ascontiguousarray(source,dtype=np.float32)
        limit=np.broadcast_to(np.float32(limit),source.shape).copy()
        rows=[]
        for fn in self.functions:
            out=np.zeros_like(source)
            fn(source.ctypes.data,out.ctypes.data,len(source),limit.ctypes.data)
            self.assertTrue(np.isfinite(out).all());rows.append(out)
        return rows

    def test_all_eleven_modes_against_original(self):
        n=64000;t=np.arange(n,dtype=np.float32)
        source=np.c_[2*np.sin(t*.031),.4*np.sin(t*.071)].astype(np.float32)
        source[16000:20000]=0;source[30000:40000]*=.001
        for mode in range(11):
            for drive in (0,.3,.8,1):
                if mode==6 and drive==1:continue # upstream fmod(x,0), tested separately below
                with self.subTest(mode=mode,drive=drive):
                    rows=[]
                    for fn in self.mode_functions:
                        out=np.zeros_like(source)
                        fn(source.ctypes.data,out.ctypes.data,n,mode,drive)
                        self.assertTrue(np.isfinite(out).all());rows.append(out)
                    np.testing.assert_allclose(rows[1],rows[0],atol=3e-4,rtol=2e-3)

    def test_output_under_address_and_undefined_sanitizers(self):
        output=ROOT/'build/msplus/plateau-output-sanitized'
        subprocess.run(['c++','-O1','-g','-std=c++14','-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer','-DPL_DERIVED','-DPL_SANITIZE_MAIN',
                        '-I'+str(ROOT/'src/msplus/plateau'),
                        str(ROOT/'tools/msplus/plateau_output_oracle.cpp'),'-o',str(output)],check=True)
        subprocess.run([str(output)],check=True)

    def test_full_drive_fold_is_finite(self):
        source=np.ones((32000,2),np.float32)*.1
        out=np.zeros_like(source)
        self.mode_functions[1](source.ctypes.data,out.ctypes.data,len(source),6,1)
        self.assertTrue(np.isfinite(out).all())
        self.assertLess(np.max(abs(out)),1e-4)

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
