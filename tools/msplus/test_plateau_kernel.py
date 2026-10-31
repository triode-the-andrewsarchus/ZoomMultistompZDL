"""Whole 44.1 kHz adapter: startup, stereo paths, levels, clear and guards."""
import unittest

import numpy as np
from native import Kernel


class PlateauKernelTests(unittest.TestCase):
    def make(self):
        kernel=Kernel('plateau',arena_bytes=705600)
        self.run_audio(kernel,np.zeros((6400,2),np.float32))
        return kernel

    def run_audio(self,kernel,source):
        source=np.asarray(source,dtype=np.float32)
        self.assertEqual(len(source)%16,0)
        result=np.concatenate([kernel.block(source[i:i+16]) for i in range(0,len(source),16)])
        self.assertTrue(np.isfinite(result).all());self.assertLess(np.max(abs(result)),2)
        self.assertEqual(kernel.state[2],0,'DSP stability guard fired')
        np.testing.assert_array_equal(kernel.arena[:2],0xcafef00d)
        np.testing.assert_array_equal(kernel.arena[-2:],0xcafef00d)
        self.assertEqual(kernel.arena[2],0,'raw control header was not erased')
        return result

    def test_dry_round_trip_gain_delay_and_isolation(self):
        kernel=self.make();kernel.coeff[5]=0
        self.run_audio(kernel,np.zeros((32000,2)))
        t=np.arange(44160)/44100
        source=np.c_[.01*np.sin(2*np.pi*1000*t),np.zeros(len(t))]
        out=self.run_audio(kernel,source)
        gain=np.sqrt(np.mean(out[8000:,0]**2))/np.sqrt(np.mean(source[8000:,0]**2))
        self.assertLess(abs(20*np.log10(gain)),.05)
        np.testing.assert_array_equal(out[:,1],0)
        self.run_audio(kernel,np.zeros((4000,2)))
        impulse=np.zeros((2048,2));impulse[0,0]=.01
        out=self.run_audio(kernel,impulse)
        self.assertGreater(np.argmax(abs(out[:,0])),490)
        self.assertLess(np.argmax(abs(out[:,0])),540)

    def test_wet_impulse_has_stereo_tail(self):
        kernel=self.make();kernel.coeff[5]=1
        self.run_audio(kernel,np.zeros((32000,2)))
        source=np.zeros((88208,2));source[0,0]=.01
        out=self.run_audio(kernel,source)
        energy=np.sqrt(np.mean(out[10000:40000]**2,axis=0))
        self.assertTrue((energy>1e-6).all())
        self.assertLess(abs(np.corrcoef(out[10000:40000].T)[0,1]),.99)

    def test_clear_removes_tail_and_does_not_repeat(self):
        kernel=self.make();kernel.coeff[5]=1;kernel.coeff[11]=.5
        source=np.zeros((16000,2));source[0,0]=.02
        self.run_audio(kernel,source)
        kernel.coeff[11]=1
        out=self.run_audio(kernel,np.zeros((16000,2)))
        self.assertLess(np.max(abs(out[-4000:])),1e-8)
        # Hold CLEAR while adding another impulse: this must not keep clearing.
        source=np.zeros((32000,2));source[0,0]=.01
        out=self.run_audio(kernel,source)
        self.assertGreater(np.max(abs(out[1000:])),1e-5)

    def test_level_and_live_parameter_changes(self):
        kernel=self.make();t=np.arange(16000)/44100
        source=np.c_[.01*np.sin(2*np.pi*137*t),.003*np.sin(2*np.pi*431*t)]
        kernel.coeff[13]=6/8 # Edit LIMIT, then move Value in a later callback.
        self.run_audio(kernel,np.zeros((16,2)))
        kernel.coeff[14]=.6
        for level in (.25,.5,.75,1):
            kernel.coeff[12]=level
            out=self.run_audio(kernel,source)
            self.assertGreater(np.sqrt(np.mean(out[-4000:]**2)),1e-7)
        kernel.coeff[6]=1;kernel.coeff[10]=1;kernel.coeff[11]=.5
        self.run_audio(kernel,source)

    def test_bad_coefficients_and_insufficient_grant_are_silent(self):
        kernel=self.make();before=kernel.arena.copy();kernel.coeff[5]=np.nan
        out=kernel.block(np.ones((16,2))*.1)
        np.testing.assert_array_equal(out,0);np.testing.assert_array_equal(before,kernel.arena)
        kernel.coeff[5]=.5;kernel.descriptor[1]=kernel.descriptor[0]+64;kernel.descriptor[2]=64
        out=kernel.block(np.ones((16,2))*.1)
        np.testing.assert_array_equal(out,0);np.testing.assert_array_equal(before,kernel.arena)


if __name__=='__main__':unittest.main()
