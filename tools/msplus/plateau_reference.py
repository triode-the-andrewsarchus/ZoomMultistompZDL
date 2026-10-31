"""Reviewed plate-reverb HIL cases and native/reference audio comparisons."""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal
from native import Kernel
from reference import harmonic_rms
from wavefold_reference import capture_coefficients

CASES=[
    ('dry',[(2,0),(3,500),(4,563),(5,0),(6,5),(7,0),(8,0),(9,500),(10,6),(11,0)],'sweep'),
    ('limited',[(9,1000),(11,995)],'tone'),
    ('reset-default',[(8,2),(9,500),(11,0),(2,1000)],'silence'),
    ('wet',[(8,0)],'sweep'),
    ('reset-pre',[(8,2)],'silence'),
    ('predelay',[(8,0),(5,500)],'sweep'),
    ('reset-level',[(8,2)],'silence'),
    ('quiet-level',[(8,0),(5,0),(9,250)],'sweep'),
    ('reset-filter',[(8,2)],'silence'),
    ('filtered',[(8,0),(9,500),(10,2),(11,700)],'sweep'),
    ('motion',[(11,0),(3,1000),(4,900),(5,500),(6,1000),(7,1000)],'probe'),
    ('freeze',[(8,1)],'tone'),
    ('clear',[(8,2)],'silence'),
    ('dry-final',[(8,0),(2,0),(3,500),(4,563),(5,0),(6,5),(7,0),(9,500)],'sweep'),
]
STATIC_CASES={'wet','predelay','quiet-level','filtered'}


def render(kernel,samples):
    samples=np.asarray(samples,dtype=np.float32)
    return np.concatenate([kernel.block(samples[i:i+16]) for i in range(0,len(samples),16)])


def reference_impulses(directory):
    cases=json.loads((directory/'CASES.json').read_text())
    if cases!=json.loads(json.dumps(CASES)):
        raise ValueError('Plateau capture cases differ from the reviewed sequence')
    kernel=Kernel('plateau',arena_bytes=705600);impulses={}
    for label,edits,_ in cases:
        for parameter,value in edits:
            index=parameter-2;kernel.coeff[5+index]=value/kernel.manifest['params'][index]['max']
            kernel.block(np.zeros((16,2),np.float32))
        render(kernel,np.zeros((44160,2),np.float32))
        if label in STATIC_CASES:
            source=np.zeros((529200,2),np.float32);source[0,0]=.001
            impulses[label]=render(kernel,source)/.001
        if kernel.state[2]:raise ValueError('Native Plateau stability guard fired')
    return impulses


def spectral_comparison(baseline,actual,impulse,rate):
    # Both pedal inputs feed the original mono plate tank. Physical input/output
    # gain differences are below 0.1 dB on the independently calibrated rig.
    converted=signal.resample_poly(impulse,160,147,axis=0)*(147/160)
    predicted=np.column_stack([signal.fftconvolve(baseline.sum(axis=1),converted[:,ch])[:len(actual)] for ch in range(2)])
    frequencies=np.fft.rfftfreq(len(actual),1/rate)
    noise=abs(np.fft.rfft(baseline[-rate:],n=len(actual),axis=0))**2*len(actual)/rate
    model=abs(np.fft.rfft(predicted,axis=0))**2;measured=abs(np.fft.rfft(actual,axis=0))**2
    rows=[]
    for ch in range(2):
        for center in (100,200,400,800,1600,3200,6400,12800):
            band=(frequencies>center/2**(1/6))&(frequencies<center*2**(1/6))
            target=float(model[band,ch].sum());background=float(noise[band,ch].sum())
            if target<16*background:continue
            error=10*np.log10(max(float(measured[band,ch].sum())-background,1e-30)/target)
            rows.append(dict(channel=ch,center_hz=center,error_db=float(error)))
    return rows


def validate_plateau(directory):
    baseline,rate=sf.read(directory/'baseline/return.wav',always_2d=True)
    if rate!=48000:raise ValueError('Plateau reference requires the verified 48 kHz rig')
    noise=np.sqrt(np.mean(baseline[-rate:]**2,axis=0));rows=[];errors=[]
    for label,impulse in reference_impulses(directory).items():
        actual,actual_rate=sf.read(directory/label/'return.wav',always_2d=True)
        if actual_rate!=rate:raise ValueError('Plateau capture sample rates differ')
        bands=spectral_comparison(baseline,actual,impulse,rate)
        if len(bands)<8:errors.append(label+': insufficient measurable reference bands')
        for band in bands:
            rows.append(dict(capture=label,**band))
            if abs(band['error_db'])>1:errors.append('Plateau frequency-response mismatch: '+str(rows[-1]))
    for label,_,kind in CASES:
        if kind!='silence':continue
        actual,actual_rate=sf.read(directory/label/'return.wav',always_2d=True)
        rms=np.sqrt(np.mean(actual[-2*rate:]**2,axis=0))
        rows.append(dict(capture=label,cleared_rms=rms.tolist(),noise_rms=noise.tolist()))
        if actual_rate!=rate or np.any(rms>noise*3):errors.append(label+': reverb did not clear to the measured noise floor')
    for label in ('motion','freeze'):
        actual,_=sf.read(directory/label/'return.wav',always_2d=True)
        if np.sqrt(np.mean(actual**2))<5*noise.max():errors.append(label+': missing processed output')
    return rows,errors


def compare_limiter(directory,calibration,output_probe=None):
    gains=np.asarray(json.loads(Path(calibration).read_text())['bus_to_return'])
    if gains.shape!=(2,) or not np.isfinite(gains).all() or np.any((gains<.5)|(gains>2)):
        raise ValueError('Invalid independently measured output gains')
    baseline,rate=sf.read(directory/'baseline-tone/return.wav',always_2d=True)
    actual,actual_rate=sf.read(directory/'limited/return.wav',always_2d=True)
    if rate!=actual_rate:raise ValueError('Plateau limiter capture rates differ')
    kernel=Kernel('plateau',arena_bytes=705600);coeff=capture_coefficients(directory,kernel)['limited'];rows=[];errors=[]
    for ch in range(2):
        start=int((.8+ch*2.5)*rate)
        amplitude=harmonic_rms(baseline[start:start+int(.8*rate),ch],rate,997,1)[0]*np.sqrt(2)/gains[ch]
        kernel.state[:]=0;kernel.state[kernel.guard_word]=kernel.guard;kernel.coeff[:]=coeff;kernel.coeff[14]=0
        render(kernel,np.zeros((6400,2),np.float32));kernel.coeff[14]=coeff[14]
        render(kernel,np.zeros((44160,2),np.float32))
        source=np.zeros((44160,2),np.float32);source[:,ch]=amplitude*np.sin(2*np.pi*997*np.arange(44160)/44100)
        predicted=render(kernel,source)[-35280:,ch]*gains[ch]
        target=harmonic_rms(predicted,44100,997,1)[0]
        measured=harmonic_rms(actual[start:start+int(.8*rate),ch],rate,997,1)[0]
        error=float(20*np.log10(max(measured,1e-15)/max(target,1e-15)))
        rows.append(dict(channel=ch,predicted_rms=float(target),measured_rms=float(measured),error_db=error))
        if abs(error)>1:errors.append('Plateau calibrated limiter mismatch: '+str(rows[-1]))
    return rows,errors
