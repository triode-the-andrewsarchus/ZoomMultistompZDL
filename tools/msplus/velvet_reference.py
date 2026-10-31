"""Pinned upstream oracle and recorded mono-to-stereo/filter hardware checks."""
import ctypes
import json
import subprocess

import numpy as np
import soundfile as sf
from scipy import signal
from native import ROOT
from audio import analyze as analyze_audio

CASES = [
    ('dry', [(2,0),(5,0),(10,2)], 'sweep'),
    ('mono-dry-l', [(10,0)], 'sweep'),
    ('mono-l', [(2,100)], 'sweep'),
    ('mono-dry-r', [(2,0),(10,1)], 'sweep'),
    ('mono-r', [(2,100)], 'sweep'),
    ('dense-dry', [(2,0),(3,1000),(4,1000),(8,0),(10,0)], 'sweep'),
    ('dense', [(2,100)], 'sweep'),
    ('evolving', [(5,1),(6,1),(7,90)], 'probe'),
    ('stereo', [(3,276),(4,272),(5,0),(8,60),(10,2)], 'sweep'),
]


class VelvetReference:
    """Compile the unmodified portable C++ core; no VST SDK or hardware access."""
    def __init__(self):
        dependency=ROOT/'build/msplus/velvet'
        pin=json.loads((ROOT/'tools/msplus/upstream.lock.json').read_text())['velvet']
        actual=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:
            raise RuntimeError('Velvet reference is not the pinned upstream source')
        subprocess.run(['git','-C',str(dependency),'diff','--exit-code','HEAD','--','src','include'],check=True)
        output=ROOT/'build/msplus/velvet-oracle.so'
        subprocess.run(['c++','-shared','-fPIC','-O2','-std=c++17','-I'+str(dependency/'include'),
                        str(ROOT/'tools/msplus/velvet_oracle.cpp'),str(dependency/'src/processor.cpp'),
                        '-o',str(output)],check=True)
        self.library=ctypes.CDLL(str(output))
        self.fn=self.library.velvet_reference
        self.fn.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint,ctypes.c_int]

    def render(self,samples,controls,variant=0,dynamic=False):
        samples=np.ascontiguousarray(samples,dtype=np.float32)
        controls=np.ascontiguousarray(controls,dtype=np.float64)
        output=np.zeros_like(samples)
        self.fn(samples.ctypes.data,output.ctypes.data,len(samples),controls.ctypes.data,variant,int(dynamic))
        return output


def mono_route(directory,label):
    folder=directory/label
    sent,rate=sf.read(folder/'send.wav',always_2d=True)
    returned,actual_rate=sf.read(folder/'return.wav',always_2d=True)
    if rate!=actual_rate:
        raise ValueError('Velvet routing sample rates differ')
    report=analyze_audio(sent,returned,rate)
    paths=[p for p in report['paths'] if p['correlation']>.8 and -30<p['gain_db']<-10]
    identities=sorted((p['send'],p['capture']) for p in paths)
    if identities not in ([(0,0),(0,1)],[(1,0),(1,1)]):
        raise ValueError('Selected mono input does not feed both physical returns: '+label)
    return identities[0][0]


def band_errors(directory,dry,wet,impulse,orientation):
    reference,rate=sf.read(directory/dry/'return.wav',always_2d=True)
    actual,actual_rate=sf.read(directory/wet/'return.wav',always_2d=True)
    if rate!=actual_rate or rate!=48000:
        raise ValueError('Velvet reference expects the verified 48 kHz rig')
    # Preserve DC gain while converting the 44.1 kHz discrete impulse response.
    converted=signal.resample_poly(impulse,160,147,axis=0)*(147/160)
    size=2**int(np.ceil(np.log2(len(reference)+len(converted))))
    model=np.fft.rfft(converted,n=size,axis=0)
    source=np.fft.rfft(reference,n=size,axis=0)
    captured=np.fft.rfft(actual,n=size,axis=0)
    frequencies=np.fft.rfftfreq(size,1/rate)
    rows=[]
    for channel in range(2):
        predicted=abs(source[:,channel]*model[:,channel^orientation])**2
        measured=abs(captured[:,channel])**2
        for center in (100,200,400,800,1600,3200,6400,12800):
            band=(frequencies>center/2**(1/6)) & (frequencies<center*2**(1/6))
            error=10*np.log10(max(measured[band].sum(),1e-30)/max(predicted[band].sum(),1e-30))
            rows.append(dict(capture=wet,channel=channel,center_hz=center,error_db=float(error)))
    return rows


def validate_velvet(directory):
    if json.loads((directory/'CASES.json').read_text())!=json.loads(json.dumps(CASES)):
        raise ValueError('Velvet captures differ from reviewed cases')
    for label in ['baseline']+[case[0] for case in CASES]:
        recording,rate=sf.read(directory/label/'return.wav',always_2d=True)
        report=json.loads((directory/label/'report.json').read_text())
        if (rate!=48000 or report['xruns'] or not np.isfinite(recording).all()
                or np.max(abs(recording))>=.999):
            raise ValueError('Invalid actual Velvet recording: '+label)
    left=mono_route(directory,'mono-dry-l');right=mono_route(directory,'mono-dry-r')
    if left==right:
        raise ValueError('Mono L/R selectors did not select distinct inputs')
    oracle=VelvetReference()
    stimulus=np.zeros((8192,2),np.float32);stimulus[0]=1
    default=oracle.render(stimulus,[1,27.6,1088,5,250,60])
    dense=oracle.render(stimulus,[1,100,4000,5,250,0])
    orientations=[]
    for orientation in (0,1):
        rows=[]
        for dry,wet,impulse in [('mono-dry-l','mono-l',default),('mono-dry-r','mono-r',default),
                                ('dense-dry','dense',dense)]:
            rows.extend(band_errors(directory,dry,wet,impulse,orientation))
        orientations.append(rows)
    rows=min(orientations,key=lambda r:max(abs(x['error_db']) for x in r))
    errors=['Velvet upstream frequency-response mismatch: '+str(r) for r in rows if abs(r['error_db'])>1]
    audio,rate=sf.read(directory/'evolving/return.wav',always_2d=True)
    start=int((.8+left*2.5)*rate);end=start+rate
    segment=audio[start:end]
    correlation=float(np.corrcoef(segment.T)[0,1])
    rows.append(dict(capture='evolving',mono_send=left,channel_correlation=correlation))
    if not abs(correlation)<=.6:
        errors.append('Velvet dense dynamic mono-to-stereo decorrelation is missing')
    baseline,_=sf.read(directory/'baseline/return.wav',always_2d=True)
    noise=np.sqrt(np.mean(baseline[-rate:]**2,axis=0))
    windows=segment[:len(segment)//960*960].reshape(-1,960,2)
    minimum=np.sqrt(np.mean(windows**2,axis=1)).min(axis=0)
    rows.append(dict(capture='evolving',minimum_20ms_rms=minimum.tolist()))
    if np.any(minimum<noise*5):
        errors.append('Velvet renewal caused a dropout or silence')
    stereo,_=sf.read(directory/'stereo/return.wav',always_2d=True)
    for channel in range(2):
        slot=stereo[int((.8+channel*2.5)*rate):int((1.8+channel*2.5)*rate)]
        rms=np.sqrt(np.mean(slot**2,axis=0))
        leakage=float(20*np.log10(max(rms[1-channel],1e-15)/max(rms[channel],1e-15)))
        rows.append(dict(capture='stereo',send=channel,cross_channel_db=leakage))
        if leakage>-25:
            errors.append('Velvet stereo input mode has unexpected channel mixing')
    return rows,errors
