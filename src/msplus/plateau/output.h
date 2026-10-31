/* Plateau/Campestria output DSP, GPL-3.0-or-later (see LICENSE.md).
 * Box-prefix arithmetic follows Signalsmith DSP 1.6.0, MIT, copyright
 * 2021 Geraint Luff / Signalsmith Audio Ltd.; see LICENSE-Signalsmith.txt.
 * Fixed storage replaces dynamic allocation. The peak window is a bounded
 * minimum tree: exactly the same 320-sample window, at most nine updates.
 * Caller validates all input/control values and initializes before use. */
#ifndef MSPLUS_PLATEAU_OUTPUT_H
#define MSPLUS_PLATEAU_OUTPUT_H
#include "core_support.h"
struct PlateauBox {
    float *history,sum,wrap,multiplier;
    unsigned index,length;
};
struct PlateauSoftLimiter {
    float *peak,*delay,release;
    PlateauBox boxes[3];
    unsigned peakwrite,delaywrite;
};
/* Float-only histories stay outside the encoded control header. Non-audio
 * histories are scaled to inaudible values, including the delay before gain
 * reduction, so firmware reusing the arena cannot interpret a gain sum as audio. */
struct PlateauSoftMemory {float peak[1024],delay[321],boxes[3][131];};
static PL_INLINE float po_min(float a,float b){return a<b?a:b;}
static PL_INLINE float po_abs(float a){return a<0?-a:a;}
static PL_INLINE void po_soft_init(PlateauSoftLimiter *s,PlateauSoftMemory *memory){
    s->peak=memory->peak;s->delay=memory->delay;
    unsigned i,j;
    for(i=0;i<1024;++i)((volatile float*)s->peak)[i]=1e-20f;
    for(i=0;i<321;++i)((volatile float*)s->delay)[i]=0;
    static const unsigned lengths[]={130,108,84};
    for(i=0;i<3;++i){
        PlateauBox *b=&s->boxes[i];b->history=memory->boxes[i];b->length=lengths[i];b->multiplier=p_recip((float)b->length);b->index=0;b->sum=0;
        b->wrap=(float)(b->length+1)*1e-20f;
        for(j=0;j<131;++j)((volatile float*)b->history)[j]=(float)j*1e-20f;
    }
    s->release=1;s->peakwrite=s->delaywrite=0;
}
static PL_INLINE float po_box(PlateauBox *s,float x){
    if(++s->index==s->length+1){s->index=0;s->wrap=s->sum;s->sum=0;}
    s->sum+=x*1e-20f;s->history[s->index]=s->sum;
    int read=(int)s->index-(int)s->length;
    float total=s->sum;
    if(read<0){read+=(int)s->length+1;total+=s->wrap;}
    return (total-s->history[read])*(s->multiplier*1e20f);
}
static PL_INLINE float po_soft(PlateauSoftLimiter *s,float x,float limit){
    float magnitude=po_abs(x);
    float gain=magnitude>limit?limit*p_recip(magnitude):1;
    unsigned node=512+s->peakwrite;
    s->peak[node]=gain*1e-20f;
    for(node>>=1;node;node>>=1)s->peak[node]=po_min(s->peak[2*node],s->peak[2*node+1]);
    if(++s->peakwrite==320)s->peakwrite=0;
    gain=s->peak[1]*1e20f;
    s->release+=(gain-s->release)*(1.0f/19201.0f);
    s->release=po_min(s->release,gain);
    gain=s->release;
    for(unsigned i=0;i<3;++i)gain=po_box(&s->boxes[i],gain);
    s->delay[s->delaywrite]=x*1e-10f;
    if(++s->delaywrite==321)s->delaywrite=0;
    return s->delay[s->delaywrite]*(gain*1e10f);
}

struct PlateauDynamics {
    float *average,dcin,dcout,sum,correction,env;
    unsigned write;
};
struct PlateauRipped {unsigned count;float gate;};
struct PlateauOutput {
    PlateauSoftLimiter soft[2];
    PlateauDynamics dynamics;
    PlateauRipped ripped[2];
};
struct PlateauOutputMemory {PlateauSoftMemory soft[2];float average[9600];};
static PL_INLINE void po_output_init(PlateauOutput *s,PlateauOutputMemory *memory){
    for(unsigned i=0;i<2;++i){po_soft_init(&s->soft[i],&memory->soft[i]);s->ripped[i].count=0;s->ripped[i].gate=0;}
    s->dynamics.average=memory->average;s->dynamics.write=0;
    s->dynamics.dcin=s->dynamics.dcout=s->dynamics.sum=s->dynamics.correction=s->dynamics.env=0;
    for(unsigned i=0;i<9600;++i)((volatile float*)memory->average)[i]=0;
}
static PL_INLINE float po_saturator(float sample){
    float x=po_abs(sample)*(1.0f/12.0f),x1=(x+1)*.5f;
    float value=12*(.075f/12+x1-p_sqrt(x1*x1-.98765f*x)*(1.0f/.98765f));
    return sample<0?-value:value;
}
/* Preserve the original 8192-entry amplifier's quantization and low-dB ramp.
 * Evaluate its quantized table entry rather than allocating a writable table. */
static PL_INLINE float po_amplifier(float db){
    if(db<=-60)return 0;
    int index=(int)((db+60)*(8192.0f/80.0f));if(index>8191)index=8191;
    float entry=-60+(float)index*(80.0f/8192.0f);
    if(entry<=-54)return ((entry+60)*(1.0f/6.0f))*p_exp2(-54*(3.321928094887f/20));
    return p_exp2(entry*(3.321928094887f/20));
}
static PL_INLINE void po_lmtr(PlateauDynamics *s,float *left,float *right,float threshold){
    float input=*left+*right;
    s->dcout=input-s->dcin+.999f*s->dcout;s->dcin=input;
    float value=po_abs(s->dcout)*1e-10f;
    /* Compensated summation prevents a 300 ms running window drifting during
     * long unattended use after converting the upstream double sum to float. */
    float delta=(value-s->average[s->write])-s->correction;
    float total=s->sum+delta;s->correction=(total-s->sum)-delta;s->sum=total;
    s->average[s->write]=value;if(++s->write==9600)s->write=0;
    float env=s->sum*(1e10f/9600.0f),last=s->env;
    env=env>last?po_min(last+10.0f/4800.0f,env):-po_min(-last+10.0f/19200.0f,-env);
    s->env=env;
    float detector=env*.2f;
    float db=detector<1e-6f?-120:6.02059991328f*p_log2(detector);
    float compression=db>threshold?(db-threshold)*.999f:0;
    float gain=po_amplifier(-compression);
    float pair[]={*left,*right};
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned channel=0;channel<2;++channel)pair[channel]=po_saturator(gain*pair[channel]);
    float a=pair[0],b=pair[1];
    /* Upstream processChannel's output references are declared right,left,
     * while its call site supplies left,right. Retain that actual ordering. */
    *left=b;*right=a;
}
static PL_INLINE float po_clip(float x,float threshold){return x>threshold?threshold:(x< -threshold?-threshold:x);}
static PL_INLINE float po_saturation(float x){return x*(27+x*x)*p_recip(27+9*x*x);}
static PL_INLINE float po_fold(float x,float threshold){
    if(threshold<=0)return 0; /* original fmod(x,0) produces NaN at full drive */
    if(po_abs(x)<=threshold)return x;
    float numerator=x-threshold,period=threshold*4;
    int quotient=(int)(numerator*p_recip(period));
    return po_abs(po_abs(numerator-(float)quotient*period)-threshold*2)-threshold;
}
static PL_INLINE float po_ripped(PlateauRipped *s,float x,float threshold){
    float value=1;
    if(s->count<32){++s->count;value=0;}else if(s->count==32)++s->count;
    if(po_abs(x)>threshold){s->count=0;value=0;}
    s->gate=.15f*value+.85f*s->gate;return x*s->gate;
}
static PL_INLINE void po_process(PlateauOutput *s,float *left,float *right,unsigned mode,float drive){
    /* pre-LMTR, clip, saturation, fold, ripped, post-LMTR */
    static const unsigned stages[]={0,2,38,36,3,34,40,48,52,54,17};
    unsigned flags=stages[mode];
    float a=*left,b=*right,one=1-drive,mix=1-one*one*one;
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned phase=0;phase<2;++phase){
      if((phase==0&&(flags&1))||(phase==1&&(flags&32)))
          po_lmtr(&s->dynamics,&a,&b,mode==10?-30:-24);
      if(phase==0){
    if(flags&2){
        float threshold=one*one,boost=1+p_recip(threshold+1e-9f)*(1.2f-drive);
        if(mode==9)threshold+=.1f;
        a=po_clip(a,threshold)*boost;b=po_clip(b,threshold)*boost;
    }
    if(flags&8){a=po_fold(a,one);b=po_fold(b,one);}
    if(flags&(4|16)){
        float x=a,y=b;
        if(flags&16){
            float threshold=2+2*drive*drive-4*drive;
            x=po_ripped(&s->ripped[0],x,threshold);y=po_ripped(&s->ripped[1],y,threshold);
        }
        if(flags&4){
            float boost=1+drive*(flags&16?15:20),scale=1-1.6f*mix+.83f*mix*mix;
            x=po_saturation(x*boost)*scale;y=po_saturation(y*boost)*scale;
        }
        float blend=flags&16?po_min(2*mix,1):mix;
        a=a*(1-blend)+x*blend;b=b*(1-blend)+y*blend;
    }
      }
    }
    float limit=mode==0?.85f-.85f*drive:.85f;
    float pair[]={a,b};
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned channel=0;channel<2;++channel)pair[channel]=po_soft(&s->soft[channel],pair[channel],limit);
    *left=pair[0];*right=pair[1];
}
#endif
