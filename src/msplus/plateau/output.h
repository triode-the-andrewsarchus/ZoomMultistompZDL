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
static PL_INLINE void po_soft_bind(PlateauSoftLimiter *s,PlateauSoftMemory *memory){
    s->peak=memory->peak;s->delay=memory->delay;
    static const unsigned lengths[]={130,108,84};
    for(unsigned i=0;i<3;++i){
        PlateauBox *b=&s->boxes[i];b->history=memory->boxes[i];b->length=lengths[i];
        b->multiplier=p_recip((float)b->length);b->index=0;b->sum=0;
        b->wrap=(float)(b->length+1)*1e-20f;
    }
    s->release=1;s->peakwrite=s->delaywrite=0;
}
static PL_INLINE void po_soft_init(PlateauSoftLimiter *s,PlateauSoftMemory *memory){
    po_soft_bind(s,memory);
    for(unsigned i=0;i<1024;++i)((volatile float*)memory->peak)[i]=1e-20f;
    for(unsigned i=0;i<321;++i)((volatile float*)memory->delay)[i]=0;
    for(unsigned i=0;i<3;++i)for(unsigned j=0;j<131;++j)((volatile float*)memory->boxes[i])[j]=(float)j*1e-20f;
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

struct PlateauOutput {PlateauSoftLimiter soft[2];};
struct PlateauOutputMemory {PlateauSoftMemory soft[2];};
enum {PO_SOFT_WORDS=1738,PO_OUTPUT_WORDS=2*PO_SOFT_WORDS};
static_assert(sizeof(PlateauOutputMemory)==PO_OUTPUT_WORDS*sizeof(float),"Output memory layout changed");
static PL_INLINE void po_output_bind(PlateauOutput *s,PlateauOutputMemory *memory){
    for(unsigned i=0;i<2;++i)po_soft_bind(&s->soft[i],&memory->soft[i]);
}
/* One bounded initialization slice; no DSP reads these histories until done. */
static PL_INLINE unsigned po_output_step(PlateauOutputMemory *memory,unsigned position,unsigned budget){
    for(unsigned n=0;n<budget&&position<PO_OUTPUT_WORDS;++n,++position){
        unsigned channel=position>=PO_SOFT_WORDS?1:0,index=position-channel*PO_SOFT_WORDS;
        PlateauSoftMemory *m=&memory->soft[channel];
        if(index<1024)((volatile float*)m->peak)[index]=1e-20f;
        else if(index<1345)((volatile float*)m->delay)[index-1024]=0;
        else {
            index-=1345;unsigned box=index>=262?2:(index>=131?1:0);index-=box*131;
            ((volatile float*)m->boxes[box])[index]=(float)index*1e-20f;
        }
    }
    return position;
}
static PL_INLINE void po_output_init(PlateauOutput *s,PlateauOutputMemory *memory){
    po_output_bind(s,memory);po_output_step(memory,0,PO_OUTPUT_WORDS);
}
static PL_INLINE float po_clip(float x,float threshold){return x>threshold?threshold:(x< -threshold?-threshold:x);}
/* Prior 0 dB-return calibration is linear through DSP peak 0.275. Keep the
 * normal output ceiling at 0.25, below that measured Zoom headroom. */
static PL_INLINE void po_process(PlateauOutput *s,float *left,float *right,float level,float amount){
    float pair[]={*left,*right},limit=.25f-.25f*amount;
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(unsigned channel=0;channel<2;++channel)pair[channel]=po_soft(&s->soft[channel],pair[channel]*level,limit);
    *left=pair[0];*right=pair[1];
}
#endif
