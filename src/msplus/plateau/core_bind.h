/* Per-instance binding only; the host descriptor is never changed. */
#ifndef MSPLUS_PLATEAU_CORE_BIND_H
#define MSPLUS_PLATEAU_CORE_BIND_H
#include "derived_core.h"
static PL_INLINE unsigned p_bind_core(Dattorro *d,float *data,unsigned capacity){
    InterpDelay *delays[]={&d->tank.leftApf1.delay,&d->tank.leftDelay1,&d->tank.leftApf2.delay,
        &d->tank.leftDelay2,&d->tank.rightApf1.delay,&d->tank.rightDelay1,&d->tank.rightApf2.delay,
        &d->tank.rightDelay2,&d->preDelay,&d->inApf1.delay,&d->inApf2.delay,&d->inApf3.delay,&d->inApf4.delay};
    unsigned offset=0;
    for(unsigned i=0;i<13;++i){
        if(delays[i]->l<=0 || (unsigned)delays[i]->l>capacity-offset)return 0;
        delays[i]->data=data+offset;offset+=(unsigned)delays[i]->l;
    }
    return offset;
}
/* Constructed object must be zero-backed. This sets the original 32 kHz
 * configuration without constructing/assigning temporary delay/filter objects. */
#ifdef PLATEAU_EXPLICIT_INIT
static PL_INLINE unsigned p_init_core(Dattorro *d,float *data,unsigned capacity,bool defaults=true){
    Dattorro1997Tank *t=&d->tank;
    d->sampleRate=32000;d->dattorroScaleFactor=32000.0f*(1.0f/29761.0f);
    t->maxSampleRate=t->sampleRate=32000;t->sampleRateScale=d->dattorroScaleFactor;
    t->fade=t->fadeDir=1;
    t->timePadding=16;t->maxTimeScale=4;t->fadeStep=1.0f/32000.0f;
    t->rescaleTapTimes();
    t->leftDelay1.l=t->calcMaxTime(t->leftDelay1Time);
    t->leftDelay2.l=t->calcMaxTime(t->leftDelay2Time);
    t->rightDelay1.l=t->calcMaxTime(t->rightDelay1Time);
    t->rightDelay2.l=t->calcMaxTime(t->rightDelay2Time);
    t->leftApf1.delay.l=t->calcMaxTime(t->leftApf1Time);
    t->leftApf2.delay.l=t->calcMaxTime(t->leftApf2Time);
    t->rightApf1.delay.l=t->calcMaxTime(t->rightApf1Time);
    t->rightApf2.delay.l=t->calcMaxTime(t->rightApf2Time);
    d->preDelay.l=16002;
    AllpassFilter *ap[]={&d->inApf1,&d->inApf2,&d->inApf3,&d->inApf4};
    static const int times[]={141,107,379,277};
    for(unsigned i=0;i<4;++i){
        ap[i]->delay.l=(int)(8*times[i]*d->dattorroScaleFactor);
        ap[i]->delay.setDelayTime(times[i]*d->dattorroScaleFactor);
        ap[i]->setGain(i<2?.75f:.625f);
    }
    unsigned size=p_bind_core(d,data,capacity);if(!size)return 0;
    PlateauPoleCoefficients *dc[]={&d->leftInputDCBlock.pole,&d->rightInputDCBlock.pole,&t->leftOutDCBlock.pole,&t->rightOutDCBlock.pole};
    float pole=p_expf(20*((1.0f/32000.0f)*-6.283185307179586f));
    for(unsigned i=0;i<4;++i){dc[i]->_cutoffFreq=20;dc[i]->_b1=pole;dc[i]->_a0=(1+pole)*.5f;dc[i]->_a1=-dc[i]->_a0;}
    if(defaults){
    d->setTimeScale(1.0075f);d->setPreDelay(0);d->setDecay(.877465f);
    d->enableInputDiffusion(true);d->setTankDiffusion(.7f);
    d->setTankModSpeed(1);d->setTankModDepth(.5f);d->setTankModShape(.5f);
    d->setInputFilterLowCutoffPitch(0);d->setInputFilterHighCutoffPitch(10);
    d->setTankFilterLowCutFrequency(0);d->setTankFilterHighCutFrequency(10);
    }
    return size;
}
static PL_INLINE void p_clear_signals(Dattorro *d){
    InterpDelay *delays[]={&d->tank.leftApf1.delay,&d->tank.leftDelay1,&d->tank.leftApf2.delay,
        &d->tank.leftDelay2,&d->tank.rightApf1.delay,&d->tank.rightDelay1,&d->tank.rightApf2.delay,
        &d->tank.rightDelay2,&d->preDelay,&d->inApf1.delay,&d->inApf2.delay,&d->inApf3.delay,&d->inApf4.delay};
    for(unsigned i=0;i<13;++i)delays[i]->input=delays[i]->output=0;
    OnePoleHPFilter *high[]={&d->leftInputDCBlock,&d->rightInputDCBlock,&d->inputHpf,
        &d->tank.leftLowCutFilter,&d->tank.rightLowCutFilter,&d->tank.leftOutDCBlock,&d->tank.rightOutDCBlock};
    for(unsigned i=0;i<7;++i)high[i]->clear();
    d->inputLpf.clear();d->tank.leftHighCutFilter.clear();d->tank.rightHighCutFilter.clear();
    d->leftSum=d->rightSum=d->leftOut=d->rightOut=d->tankFeed=0;
    d->tank.leftSum=d->tank.rightSum=0;
}
#endif
#endif
