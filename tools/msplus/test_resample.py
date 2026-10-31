"""Actual C SRC tests: rate accounting, gain, alias rejection and channel isolation."""
import ctypes
import subprocess
import unittest

import numpy as np
from scipy.signal import freqz
from native import ROOT
from resample_coeffs import coefficients


class ResampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wrapper=ROOT/'build/msplus/plateau-src-host.c'
        wrapper.write_text('#include "'+str(ROOT/'src/msplus/plateau/resample.h')+'"\n'
            'unsigned process(const float *in,float *out,unsigned frames){\n'
            'PlateauSRC s={0};s.phase=121;s.inwrite=s.outwrite=63;unsigned i,count=0;float a,b;\n'
            'for(i=0;i<frames;++i){if(ps_push(&s,in[2*i],in[2*i+1])){\n'
            'ps_down(&s,&a,&b);ps_store(&s,a,b);++count;}\n'
            'ps_up(&s,&out[2*i],&out[2*i+1]);}return count;}\n')
        output=ROOT/'build/msplus/plateau-src-host.so'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(wrapper),'-o',str(output)],check=True)
        cls.library=ctypes.CDLL(str(output));cls.process=cls.library.process
        cls.process.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]

    def render(self,source):
        source=np.ascontiguousarray(source,dtype=np.float32);out=np.zeros_like(source)
        count=self.process(source.ctypes.data,out.ctypes.data,len(source))
        self.assertTrue(np.isfinite(out).all())
        return out,count

    def test_rate_accounting_and_dc_gain(self):
        out,count=self.render(np.ones((44100,2))*.01)
        self.assertEqual(count,32000)
        np.testing.assert_allclose(out[4410:],.01,atol=2e-7)

    def test_audio_band_gain_and_channel_isolation(self):
        t=np.arange(44100)/44100
        for frequency in (100,1000,6000,12000):
            with self.subTest(frequency=frequency):
                source=.01*np.sin(2*np.pi*frequency*t)
                out,_=self.render(np.column_stack([source,np.zeros(len(t))]))
                ratio=np.sqrt(np.mean(out[4410:,0]**2))/np.sqrt(np.mean(source[4410:]**2))
                self.assertLess(abs(20*np.log10(ratio)),.03)
                np.testing.assert_array_equal(out[:,1],0)

    def test_above_internal_nyquist_is_rejected(self):
        t=np.arange(44100)/44100
        for frequency in (16000,17000,19000,21000):
            with self.subTest(frequency=frequency):
                source=.01*np.sin(2*np.pi*frequency*t)
                out,_=self.render(np.column_stack([source,source]))
                rejection=20*np.log10(max(np.sqrt(np.mean(out[4410:]**2)),1e-15)/(.01/np.sqrt(2)))
                self.assertLess(rejection,-65)

    def test_generated_tables_match_declared_filter_response(self):
        blob=np.fromfile(ROOT/'src/msplus/plateau/resample_coeffs.bin',dtype='<f4')
        np.testing.assert_array_equal(blob,np.concatenate([coefficients(44100).ravel(),
                                                          coefficients(32000).ravel()]))
        for rate in (32000,44100):
            for row in coefficients(rate):
                frequency,response=freqz(row,worN=8192,fs=rate)
                self.assertLess(max(abs(abs(response[frequency<12000])-1)),.001)
                self.assertAlmostEqual(float(row.sum()),1,places=6)


if __name__=='__main__':
    unittest.main()
