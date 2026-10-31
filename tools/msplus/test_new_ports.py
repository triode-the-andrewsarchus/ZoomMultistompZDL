"""Independent pinned upstream oracles and native safety checks for new ports."""
import ctypes
import subprocess
import unittest

import numpy as np
from native import Kernel, ROOT
from velvet_reference import VelvetReference


class VelvetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oracle=VelvetReference()
        # Compile-time layout observation only; the reference DSP is independent.
        wrapper=ROOT/'build/msplus/velvet-layout.c'
        wrapper.write_text('#include "'+str(ROOT/'src/msplus/velvet/velvet.c')+'"\n'
                           'unsigned vn_packed(void){return VN_PACKED;}\n'
                           'unsigned vn_header(void){return VN_HEADER;}\n')
        output=ROOT/'build/msplus/velvet-layout.so'
        subprocess.run(['cc','-shared','-fPIC','-O2','-I'+str(ROOT/'src/msplus/velvet/build'),
                        str(wrapper),'-o',str(output)],check=True)
        layout=ctypes.CDLL(str(output))
        cls.packed=layout.vn_packed();cls.header=layout.vn_header()

    def prepared(self,controls=None):
        kernel=Kernel('velvet',arena_bytes=705600)
        if controls:
            for index,value in controls.items():
                kernel.coeff[index+5]=value/kernel.manifest['params'][index]['max']
        for _ in range(2000):
            kernel.block(np.zeros((16,2)))
            saved=kernel.arena[2+self.packed//4:2+self.packed//4+self.header//2]
            words=saved[::2] | (saved[1::2]<<16)
            if words[2]==4:
                return kernel
        self.fail('Cooperative initialization did not finish')

    def reference(self,kernel,samples):
        p=kernel.coeff[5:14].astype(float)
        controls=np.array([p[0],max(1,p[1]*100),max(100,p[2]*4000),max(.1,p[4]*60),
                           max(1,p[5]*1000),p[6]*120],dtype=np.float64)
        return self.oracle.render(samples,controls,int(p[7]*1000+.5),p[3]>.5)

    def render(self,kernel,samples):
        return np.concatenate([kernel.block(b) for b in samples.reshape(-1,16,2)])

    def canaries(self,kernel):
        np.testing.assert_array_equal(kernel.arena[:2],[0xcafef00d]*2)
        np.testing.assert_array_equal(kernel.arena[-2:],[0xcafef00d]*2)
        self.assertTrue(np.isfinite(kernel.arena[2:-2].view(np.float32)).all())

    def test_static_impulse_matches_upstream_mono_to_stereo(self):
        for edits in ({3:0},{1:1000,2:1000,3:0,6:0,7:731},
                      {1:10,2:25,3:0,6:120,7:1000}):
            with self.subTest(edits=edits):
                k=self.prepared(edits)
                x=np.zeros((8192,2),np.float32);x[0,1]=.01
                expected=self.reference(k,np.repeat(x[:,1,None],2,axis=1).copy())
                actual=self.render(k,x)
                np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=1e-4)
                self.canaries(k)

    def test_dynamic_fastest_dense_renewal_matches_upstream(self):
        k=self.prepared({1:1000,2:1000,4:1,5:90,6:30})
        rng=np.random.default_rng(2050083136)
        x=rng.normal(0,.002,(44112,2)).astype(np.float32)
        expected=self.reference(k,np.repeat(x[:,1,None],2,axis=1).copy())
        actual=self.render(k,x)
        residual=np.sqrt(np.mean((actual-expected)**2))/np.sqrt(np.mean(expected**2))
        self.assertLess(residual,.001)
        self.assertLess(abs(np.corrcoef(actual.T)[0,1]),.5)
        self.canaries(k)

    def test_stereo_dry_bypass_and_mono_input_selection(self):
        x=np.random.default_rng(7).normal(0,.01,(8192,2)).astype(np.float32)
        for mode in (0,1,2):
            k=self.prepared({0:0,8:mode})
            y=self.render(k,x)
            expected=x if mode==2 else np.repeat(x[:,1-mode,None],2,axis=1)
            np.testing.assert_allclose(y,expected,atol=1e-8)
            k.coeff[0]=0
            np.testing.assert_array_equal(self.render(k,x),x)
            self.canaries(k)

    def test_invalid_controls_and_undersized_arena_fail_closed(self):
        for arena in (8,50000):
            k=Kernel('velvet',arena_bytes=arena)
            np.testing.assert_array_equal(k.block(np.ones((16,2))*.01),0)
            self.canaries(k)
        k=self.prepared()
        for bad in (float('nan'),float('inf'),-.01,1.01):
            k.coeff[7]=bad
            np.testing.assert_array_equal(k.block(np.ones((16,2))*.01),0)
        self.canaries(k)

    def test_live_mode_mix_and_input_changes_remain_bounded(self):
        k=self.prepared({1:1000,2:1000,4:1,5:90,6:0})
        source=np.random.default_rng(91).normal(0,.005,(22064,2)).astype(np.float32)
        output=[]
        for index,block in enumerate(source.reshape(-1,16,2)):
            if index%31==0:
                k.coeff[8]=(index//31)%2
                k.coeff[13]=((index//31)%3)/2
                k.coeff[5]=((index//31)%5)/4
            output.append(k.block(block))
        actual=np.concatenate(output)
        self.assertTrue(np.isfinite(actual).all())
        self.assertLess(np.max(abs(actual)),.1)
        self.assertGreater(np.sqrt(np.mean(actual**2)),.001)
        self.canaries(k)


if __name__=='__main__':
    unittest.main()
