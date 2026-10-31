#!/usr/bin/env python3
"""Derive float/leaf-compatible Plateau core from the pinned GPL upstream."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
SOURCES=['dsp/delays/AllpassFilter.hpp','dsp/filters/OnePoleFilters.hpp',
         'dsp/modulation/LFO.hpp','Dattorro.hpp','Dattorro.cpp']


def convert(text):
    text=re.sub(r'/\*.*?\*/','',text,flags=re.S)
    text=re.sub(r'//[^\n]*','',text)
    text=re.sub(r'^\s*#.*$','',text,flags=re.M)
    text=text.replace('double','float').replace('inline ','')
    text=text.replace('const float &','float ')
    text=re.sub(r'std::pow\(2\.0,\s*([^)]*)\)',r'p_exp2(\1)',text)
    text=text.replace('expf(','p_expf(')
    for old,new in [('1.0 / _revPoint','p_recip(_revPoint)'),
                    ('-1.0 / (1.0 - _revPoint)','-p_recip(1.0 - _revPoint)'),
                    ('1.0 / (fadeTime * sampleRate)','p_recip(fadeTime * sampleRate)'),
                    ('1.0 / _sampleRate','p_recip(_sampleRate)'),
                    ('1.0 / sampleRate','p_recip(sampleRate)'),
                    ('1. / sampleRate','p_recip(sampleRate)'),
                    ('1 / sampleRate','p_recip(sampleRate)')]:
        text=text.replace(old,new)
    # Remove the two upstream scratch globals; each is a local calculation.
    text=text.replace('int maxScaledOutputTap = 0;','').replace('float scaleFactor = 0.;','')
    text=text.replace('maxScaledOutputTap = *std::max_element','int maxScaledOutputTap = *std::max_element')
    text=text.replace('    scaleFactor = timeScale','    float scaleFactor = timeScale')
    text=text.replace('InterpDelay(192010,','InterpDelay(16002,')
    text=text.replace('sampleRate / dattorroSampleRate','sampleRate * (1.0f/29761.0f)')
    # Immutable tap positions do not need a per-instance array copy.
    text=text.replace('const int kOutputTaps[7] = {266, 2974, 1913, 1996, 1990, 187, 1066};',
                      '#ifndef PLATEAU_EXPLICIT_INIT\n    const int kOutputTaps[7] = {266, 2974, 1913, 1996, 1990, 187, 1066};\n#endif')
    loop='for (size_t i = 0; i < scaledOutputTaps.size(); ++i) {\n        scaledOutputTaps[i] = (int)((float)kOutputTaps[i] * sampleRateScale);\n    }'
    assignments='\n'.join(f'    scaledOutputTaps[{i}] = (int)({tap}.0f * sampleRateScale);'
                          for i,tap in enumerate((266,2974,1913,1996,1990,187,1066)))
    text=text.replace(loop,'#ifndef PLATEAU_EXPLICIT_INIT\n'+loop+'\n#else\n'+assignments+'\n#endif')
    # Return values/pointers are float throughout. Prevent literal promotion
    # from introducing double runtime helpers on the target.
    text=re.sub(r'(?<![\w.])(\d+\.\d*|\.\d+)([eE][+-]?\d+)?(?![\w.])',
                lambda m:m[0]+'f',text)
    lines=[]
    for line in text.splitlines():
        stripped=line.strip()
        if (re.match(r'(?:void|float|int)\s+[\w:]+\s*\(',stripped)
                or re.match(r'(?:Dattorro\w*::)?(?:Dattorro\w*|AllpassFilter|TriSawLFO|OnePole\w+Filter)\s*\(',stripped)):
            line=line[:len(line)-len(line.lstrip())]+'PL_INLINE '+stripped
        lines.append(line)
    text=re.sub(r'\n\s*\n\s*\n','\n\n','\n'.join(lines))
    # The bounded target initializer sets its configuration once. Use zero
    # scalar defaults there instead of a discarded default configuration,
    # preserving ordinary host construction as the independent comparison path.
    declarations, separator, definitions=text.partition('PL_INLINE Dattorro1997Tank::Dattorro1997Tank')
    declarations=re.sub(r'^(\s*(?:float|bool) \w+) = ([^;]+);',
                        r'\1 PL_DEFAULT(\2);',declarations,flags=re.M)
    text=declarations+separator+definitions
    # Heavy constructors remain available to the independent host oracle.
    # The DSP uses explicit bounded initialization, avoiding repeated filter
    # construction/assignment and its duplicated exponential approximations.
    pattern=r'\b(?:Dattorro::Dattorro|Dattorro1997Tank::Dattorro1997Tank|AllpassFilter|OnePoleLPFilter|OnePoleHPFilter|TriSawLFO)\s*\([^;{}]*\)(?:\s*:[^{]*)?\s*\{'
    matches=list(re.finditer(pattern,text))
    for match in reversed(matches):
        start=match.end();end=start;depth=1
        while depth:
            if text[end]=='{':depth+=1
            elif text[end]=='}':depth-=1
            end+=1
        body=text[start:end-1]
        alternative=''
        if match[0].startswith('TriSawLFO'):
            alternative='\n#else\n_output=phase=_step=0;_rising=true;_sampleRate=32000;_1_sampleRate=1.0f/32000;\n'
        if match[0].startswith('AllpassFilter'):
            alternative='\n#else\ninput=output=gain=_inSum=_outSum=0;\n'
        if match[0].startswith(('OnePoleLPFilter','OnePoleHPFilter')):
            alternative='\n#else\n_sampleRate=32000;_1_sampleRate_pi=(1.0f/32000.0f)*-6.283185307179586f;_maxCutoffFreq=15999;\n'
        text=text[:start]+'\n#ifndef PLATEAU_EXPLICIT_INIT\n'+body+alternative+'\n#endif\n'+text[end-1:]
    return share_loops(text)


def share_loops(text):
    """Share symmetric arithmetic without changing per-channel operation order."""
    bodies={
        'Dattorro1997Tank::tickApfModulation': '''
    TriSawLFO *lfos[]={&lfo1,&lfo2,&lfo3,&lfo4};
    InterpDelay *delays[]={&leftApf1.delay,&leftApf2.delay,&rightApf1.delay,&rightApf2.delay};
    float times[]={scaledLeftApf1Time,scaledLeftApf2Time,scaledRightApf1Time,scaledRightApf2Time};
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned i=0;i<4;++i)delays[i]->setDelayTime(lfos[i]->process()*lfoExcursion+times[i]);
''',
        'Dattorro1997Tank::process': '''
    tickApfModulation();decay=decayParam;
    leftSum+=leftIn;rightSum+=rightIn;
    AllpassFilter *first[]={&leftApf1,&rightApf1},*second[]={&leftApf2,&rightApf2};
    InterpDelay *delay1[]={&leftDelay1,&rightDelay1},*delay2[]={&leftDelay2,&rightDelay2};
    OnePoleLPFilter *lowpass[]={&leftHighCutFilter,&rightHighCutFilter};
    OnePoleHPFilter *highpass[]={&leftLowCutFilter,&rightLowCutFilter},*dc[]={&leftOutDCBlock,&rightOutDCBlock};
    float sums[]={leftSum,rightSum};
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned ch=0;ch<2;++ch){
        first[ch]->input=sums[ch];delay1[ch]->input=first[ch]->process();delay1[ch]->process();
        lowpass[ch]->input=delay1[ch]->output;highpass[ch]->input=lowpass[ch]->process();
        second[ch]->input=(delay1[ch]->output*(1.0f-fade)+highpass[ch]->process()*fade)*decay;
        delay2[ch]->input=second[ch]->process();delay2[ch]->process();
    }
    rightSum=leftDelay2.output*decay;leftSum=rightDelay2.output*decay;
    float outputs[2];
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned ch=0;ch<2;++ch){
        unsigned other=1-ch;
        dc[ch]->input=first[ch]->output;
        dc[ch]->input+=delay1[ch]->tap(scaledOutputTaps[0]);
        dc[ch]->input+=delay1[ch]->tap(scaledOutputTaps[1]);
        dc[ch]->input-=second[ch]->delay.tap(scaledOutputTaps[2]);
        dc[ch]->input+=delay2[ch]->tap(scaledOutputTaps[3]);
        dc[ch]->input-=delay1[other]->tap(scaledOutputTaps[4]);
        dc[ch]->input-=second[other]->delay.tap(scaledOutputTaps[5]);
        dc[ch]->input-=delay2[other]->tap(scaledOutputTaps[6]);
        outputs[ch]=dc[ch]->process()*.5f;
    }
    *leftOut=outputs[0];*rightOut=outputs[1];
    fade+=fadeStep*fadeDir;fade=fade<0?0:(fade>1?1:fade);
''',
    }
    for name,body in bodies.items():
        signature='PL_INLINE void '+name+'('
        if signature not in text:continue
        start=text.index('{',text.index(signature))+1
        end=text.index('\n}',start)
        original=text[start:end]
        text=text[:start]+'\n#ifdef PLATEAU_EXPLICIT_INIT\n'+body+'\n#else\n'+original+'\n#endif\n'+text[end:]
    # Four serial input allpasses perform identical work on successive values.
    original='''    inApf1.input = preDelay.output;
    inApf2.input = inApf1.process();
    inApf3.input = inApf2.process();
    inApf4.input = inApf3.process();
    tankFeed = preDelay.output * (1.f - diffuseInput) + inApf4.process() * diffuseInput;'''
    replacement='''
#ifdef PLATEAU_EXPLICIT_INIT
    AllpassFilter *apfs[]={&inApf1,&inApf2,&inApf3,&inApf4};
    float value=preDelay.output;
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned i=0;i<4;++i){apfs[i]->input=value;value=apfs[i]->process();}
    tankFeed=preDelay.output*(1.0f-diffuseInput)+value*diffuseInput;
#else
'''+original+'\n#endif'
    return text.replace(original,replacement)


def main():
    dependency=ROOT/'build/msplus/plateau'
    pin=json.loads((ROOT/'tools/msplus/upstream.lock.json').read_text())['plateau']
    actual=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
    if actual!=pin:
        raise RuntimeError('Plateau dependency differs from pinned source')
    subprocess.run(['git','-C',str(dependency),'diff','--exit-code','HEAD'],check=True)
    output=ROOT/'src/msplus/plateau/derived_core.h'
    records={name:hashlib.sha256((dependency/name).read_bytes()).hexdigest() for name in SOURCES}
    preamble='''/* Derived from digitalartifactmusic/PlateauNEVersio, based on Dale Johnson's
 * Valley Plateau. GPL-3.0-or-later, see LICENSE.md and LICENSE-GPLv3.txt.
 * Generated by tools/msplus/plateau_derive.py; do not hand-edit.
 * Float arithmetic, inline leaf methods, local scratch variables and capped
 * predelay are adaptations; the reverb topology/order is retained. */
#ifndef MSPLUS_PLATEAU_DERIVED_CORE_H
#define MSPLUS_PLATEAU_DERIVED_CORE_H
#include <array>
#include <algorithm>
#include <cstdint>
#include "core_support.h"
#define _2M_PI 6.283185307179586f
#ifdef PLATEAU_EXPLICIT_INIT
#define PL_DEFAULT(value) = {}
#else
#define PL_DEFAULT(value) = value
#endif
'''
    output.write_text(preamble+'\n'.join(convert((dependency/name).read_text()) for name in SOURCES)+'\n#endif\n')
    # Use the compiler's always_inline attribute in C++ mode. Generate local
    # syntax adaptations; keep every existing C port's tested headers intact.
    common=ROOT/'src/msplus/common'
    compat=(common/'compat.h').read_text()
    compat+='\n'+(common/'arena_state.h').read_text()
    src=(output.parent/'resample.h').read_text()
    for name,text in [('cpp_compat.h',compat),('cpp_resample.h',src)]:
        text=re.sub(r'^#pragma FUNC_ALWAYS_INLINE.*$','',text,flags=re.M)
        text=text.replace('static inline','static __attribute__((always_inline)) inline')
        (output.parent/name).write_text('/* Generated TI C++ inline syntax adaptation. */\n'+text)
    (output.parent/'DERIVED-SOURCES.json').write_text(json.dumps(dict(commit=pin,sha256=records),indent=2)+'\n')


if __name__=='__main__':
    main()
