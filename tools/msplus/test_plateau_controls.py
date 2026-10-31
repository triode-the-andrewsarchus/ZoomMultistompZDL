"""Control curves, editing retention, freeze and clear edges (no hardware)."""
import ctypes
import subprocess
import unittest

import numpy as np
from native import ROOT


class PlateauControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out=ROOT/'build/msplus/plateau-controls.so'
        subprocess.run(['c++','-shared','-fPIC','-O2','-std=c++14',
                        '-I'+str(ROOT/'src/msplus/plateau'),
                        str(ROOT/'tools/msplus/plateau_controls_oracle.cpp'),'-o',str(out)],check=True)
        cls.lib=ctypes.CDLL(str(out));cls.fn=cls.lib.plateau_controls_trace
        cls.fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]

    def render(self,rows):
        rows=np.ascontiguousarray(rows,dtype=np.float32)
        out=np.zeros((len(rows),32),np.float32)
        self.assertEqual(self.fn(rows.ctypes.data,out.ctypes.data,len(rows)),1)
        self.assertTrue(np.isfinite(out).all())
        return out

    def defaults(self,n):
        return np.tile([.5,.5,.5625,0,.005,.03125,0,.5,0,0],(n,1)).astype(np.float32)

    def test_parameter_endpoints_and_settling(self):
        rows=self.defaults(3000);rows[1:,:6]=1
        out=self.render(rows)
        np.testing.assert_allclose(out[0,:4],[1.0075,0,.8774606,.5],atol=1e-6)
        np.testing.assert_allclose(out[-1,:4],[4,.5,1,16],atol=1e-6)
        self.assertEqual(out[-1,10],1)
        self.assertTrue(np.all(np.diff(out[:,0])>=-1e-6))

    def test_advanced_edits_retain_independent_settings(self):
        rows=self.defaults(6)
        rows[1:,9]=.8                      # edit input high cut
        rows[2:,8]=4/8                    # select diffusion, keep old Value
        rows[3:,9]=.3                      # now edit diffusion
        rows[4:,8]=5/8                    # select input gain, keep Value
        rows[5,9]=.7
        out=self.render(rows)
        self.assertAlmostEqual(out[1,21],.8,places=6)
        self.assertEqual(out[2,25],1)
        self.assertAlmostEqual(out[3,25],.3,places=6)
        self.assertEqual(out[4,26],0)
        self.assertAlmostEqual(out[5,26],.7,places=6)
        self.assertAlmostEqual(out[-1,21],.8,places=6)

    def test_depth_lock_capture_and_release(self):
        rows=self.defaults(3000)
        rows[1:,8]=1                      # select depth lock
        rows[2:,9]=1                      # capture current depth
        rows[3:,5]=1                      # Depth becomes shape while locked
        rows[-1,9]=0                      # unlock at full Depth
        out=self.render(rows)
        self.assertAlmostEqual(out[2,11],.03125,places=6)
        self.assertAlmostEqual(out[-2,3],.5+15.5*.03125,places=6)
        self.assertAlmostEqual(out[-1,3],16,places=6)

    def test_freeze_and_clear_trigger_once(self):
        rows=self.defaults(3000);rows[1:,6]=.5;rows[-3:-1,6]=1;rows[-1,6]=0
        out=self.render(rows)
        self.assertEqual(out[-4,8],1);self.assertEqual(out[-4,2],1)
        self.assertEqual(out[-3,9],1);self.assertEqual(out[-2,9],0);self.assertEqual(out[-1,9],0)
        self.assertEqual(out[-1,8],0)


if __name__=='__main__':unittest.main()
