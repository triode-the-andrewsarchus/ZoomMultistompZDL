/* Test bridge: original Plateau lookahead limiter versus bounded adaptation. */
#ifdef PL_DERIVED
#include "output.h"
#else
#include <algorithm>
#include <limits>
#include "signalsmith/envelopes.h"
#include "signalsmith/delay.h"
#include "softlimiter.hpp"
#endif
extern "C" void plateau_soft_render(const float *input,float *output,unsigned frames,const float *limits){
#ifdef PL_DERIVED
    PlateauSoftLimiter s;PlateauSoftMemory memory;po_soft_init(&s,&memory);
    for(unsigned i=0;i<frames;++i)output[i]=po_soft(&s,input[i],limits[i]);
#else
    LimiterAttackHoldRelease s;s.configure(32000);
    for(unsigned i=0;i<frames;++i){s.limit=limits[i];output[i]=s.sample(input[i]);}
#endif
}
#ifdef PL_DERIVED
extern "C" void plateau_output_render(const float *input,float *output,unsigned frames,float level,float amount){
    PlateauOutput s;PlateauOutputMemory memory;po_output_bind(&s,&memory);
    unsigned position=0;
    while(position<PO_OUTPUT_WORDS)position=po_output_step(&memory,position,97);
    for(unsigned i=0;i<frames;++i){
        float a=input[2*i],b=input[2*i+1];po_process(&s,&a,&b,level,amount);
        output[2*i]=a;output[2*i+1]=b;
    }
}
#ifdef PL_SANITIZE_MAIN
#include <cmath>
#include <vector>
int main(){
    const unsigned frames=32000;
    std::vector<float> input(frames*2),output(frames*2);
    for(unsigned i=0;i<frames;++i){input[2*i]=2*std::sin(i*.031f);input[2*i+1]=.4f*std::sin(i*.071f);}
    for(float level:{0.0f,.5f,1.0f,2.0f})for(float amount:{0.0f,.3f,.8f,1.0f}){
        plateau_output_render(input.data(),output.data(),frames,level,amount);
        for(float value:output)if(!std::isfinite(value)||std::fabs(value)>.851f)return 1;
    }
}
#endif
#endif
