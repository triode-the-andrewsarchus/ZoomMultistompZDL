/* Test bridge: original Plateau output processing versus bounded adaptation. */
#ifdef PL_DERIVED
#include "output.h"
#else
#include <algorithm>
#include <limits>
#include "signalsmith/envelopes.h"
#include "signalsmith/delay.h"
#include "softlimiter.hpp"
#include "src/Lmtr.hpp"
#include "gaincontrol.hpp"
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

#include <new>
#include <cstring>
extern "C" void plateau_modes_render(const float *input,float *output,unsigned frames,unsigned mode,float drive){
#ifdef PL_DERIVED
    PlateauOutput s;PlateauOutputMemory memory;po_output_init(&s,&memory);
#else
    limiter.~Lmtr();std::memset(&limiter,0,sizeof(limiter));new(&limiter)Lmtr;limiter.init();limiter.engine.detector.reset();
    softerLimiterLeft=LimiterAttackHoldRelease();softerLimiterRight=LimiterAttackHoldRelease();
    softerLimiterLeft.configure(32000);softerLimiterRight.configure(32000);
    rippedCountLeft=rippedCountRight=0;leftValue=rightValue=1;leftGateFilter.tmp=rightGateFilter.tmp=0;
    gainMode=mode;outputAmplification=drive;
#endif
    for(unsigned i=0;i<frames;++i){
#ifdef PL_DERIVED
        float a=input[2*i],b=input[2*i+1];po_process(&s,&a,&b,mode,drive);
#else
        double a=input[2*i],b=input[2*i+1];gainControl(a,b);
#endif
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
    for(unsigned mode=0;mode<11;++mode)for(float drive:{0.0f,.3f,.8f,.99999994f,1.0f}){
        plateau_modes_render(input.data(),output.data(),frames,mode,drive);
        for(float value:output)if(!std::isfinite(value))return 1;
    }
}
#endif
