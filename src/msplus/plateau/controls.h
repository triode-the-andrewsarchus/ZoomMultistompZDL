/* Plateau control adaptation. Normalized snapshots are checked by the caller.
 * Original parameter curves and 0.0005/0.9995 smoothing are retained; setters
 * run once per host block after advancing the original internal sample count.
 * Edit selects an advanced field; a subsequent Value movement edits it. */
#ifndef MSPLUS_PLATEAU_CONTROLS_H
#define MSPLUS_PLATEAU_CONTROLS_H
#include "core_bind.h"
enum {PC_IN_HI,PC_IN_LO,PC_TANK_HI,PC_TANK_LO,PC_DIFF,PC_INPUT,PC_LIMIT,PC_SHAPE,PC_LOCK};
struct PlateauControls {
    float advanced[9],target[9],smooth[6],lastvalue,lockedDepth;
    unsigned edit,hold,initialized;
};
static PL_INLINE void pc_init(PlateauControls *s){
    for(unsigned i=0;i<9;++i)s->advanced[i]=s->target[i]=i==PC_DIFF?1:(i==PC_SHAPE?.5f:0);
    for(unsigned i=0;i<6;++i)s->smooth[i]=0;
    s->lastvalue=0;s->lockedDepth=0;s->edit=0;s->hold=0;s->initialized=0;
}
static PL_INLINE void pc_filters(Dattorro *d,const float advanced[9]){
    float frequencies[4];
    for(unsigned i=0;i<4;++i){float pitch=(i&1)?10*advanced[i]:10-10*advanced[i];frequencies[i]=440*p_exp2(pitch-5);}
    d->inputHighCut=frequencies[0];d->inputLowCut=frequencies[1];
    PlateauPoleCoefficients *filters[]={&d->inputLpf.pole,&d->inputHpf.pole,&d->tank.leftHighCutFilter.pole,
        &d->tank.rightHighCutFilter.pole,&d->tank.leftLowCutFilter.pole,&d->tank.rightLowCutFilter.pole};
    static const unsigned mapping[]={0,1,2,2,3,3};
    for(unsigned i=0;i<6;++i){
        PlateauPoleCoefficients *p=filters[i];float frequency=frequencies[mapping[i]];
        if(frequency!=p->_cutoffFreq){
            p->_cutoffFreq=frequency;p->_b1=p_expf(frequency*p->_1_sampleRate_pi);
            p->_a0=(i==1||i>=4)?(1+p->_b1)*.5f:1-p->_b1;p->_a1=-p->_a0;
        }
    }
}
/* UI editing is independent of the continuously smoothed DSP settings. */
static PL_INLINE unsigned pc_edit(PlateauControls *s,const float knobs[10]){
    unsigned edit=(unsigned)(int)(knobs[8]*8+.5f),hold=(unsigned)(int)(knobs[6]*2+.5f);
    unsigned clear=hold==2&&s->hold!=2;
    if(s->initialized&&edit==s->edit&&knobs[9]!=s->lastvalue){
        if(edit==PC_LOCK){
            if(knobs[9]>=.5f&&s->target[PC_LOCK]<.5f)s->lockedDepth=s->smooth[4];
            s->target[PC_LOCK]=knobs[9]>=.5f?1:0;
        }else s->target[edit]=knobs[9];
    }
    s->lastvalue=knobs[9];s->edit=edit;s->hold=hold;
    return clear;
}
static PL_INLINE void pc_smooth(float *current,const float *targets,unsigned count,unsigned frames){
    for(unsigned sample=0;sample<frames;++sample)for(unsigned i=0;i<count;++i)
        current[i]=.0005f*targets[i]+.9995f*current[i];
    /* Float recurrence otherwise stalls short of endpoints, notably freeze. */
    for(unsigned i=0;i<count;++i){
        float error=targets[i]-current[i],tolerance=.0001f*(targets[i]>1?targets[i]:1);
        if(error> -tolerance&&error<tolerance)current[i]=targets[i];
    }
}
static PL_INLINE unsigned pc_block(PlateauControls *s,Dattorro *d,const float knobs[10],unsigned frames){
    unsigned clear=pc_edit(s,knobs),hold=s->hold;
    float decay=hold==1?1:knobs[2];
    decay=.2f+.7999f*decay;decay=1-(1-decay)*(1-decay);
    float targets[]={knobs[0],.01f+3.99f*knobs[1]*knobs[1],decay,.5f*knobs[3],knobs[5],knobs[7]};
    if(!s->initialized){for(unsigned i=0;i<6;++i)s->smooth[i]=targets[i];s->initialized=1;}
    /* Advance at the internal rate, then apply the block-end settings. */
    pc_smooth(s->smooth,targets,6,frames);pc_smooth(s->advanced,s->target,8,frames);
    s->advanced[PC_LOCK]=s->target[PC_LOCK];
    d->setTimeScale(s->smooth[1]);d->setPreDelay(s->smooth[3]);d->setDecay(s->smooth[2]);
    d->setTankModSpeed(.5f+100*knobs[4]);
    bool locked=s->advanced[PC_LOCK]>=.5f;
    d->setTankModDepth(locked?.5f+15.5f*s->lockedDepth:16*s->smooth[4]);
    d->setTankModShape(.001f+.998f*(locked?s->smooth[4]:s->advanced[PC_SHAPE]));
    pc_filters(d,s->advanced);
    d->enableInputDiffusion(s->advanced[PC_DIFF]>0);
    if(s->advanced[PC_DIFF]>0)d->setTankDiffusion(.7f*s->advanced[PC_DIFF]);
    d->freeze(hold==1);
    return clear;
}
#endif
