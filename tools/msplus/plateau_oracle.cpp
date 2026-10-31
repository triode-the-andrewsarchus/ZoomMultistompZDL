/* Test-only host bridge. Original oracle changes array capacity only to fix
 * its predelay row-overrun; the DSP source and equations remain upstream. */
#include <vector>
#include <new>
#include <cstring>
#ifdef PL_DERIVED
#include "core_bind.h"
#else
#include "Dattorro.hpp"
#endif
extern "C" unsigned plateau_render(const float *input,float *output,unsigned frames,const float *p){
#ifndef PL_DERIVED
    count=0;hold=1;clearPopCancelValue=1;
#endif
    alignas(Dattorro) unsigned char storage[sizeof(Dattorro)];
    std::memset(storage,0,sizeof(storage));
    Dattorro *d=new(storage) Dattorro(32000,16,4);
#ifndef PLATEAU_EXPLICIT_INIT
    d->setSampleRate(32000);
#endif
#ifdef PL_DERIVED
    const unsigned size=144261;
    std::vector<float> arena(size+2,0);arena.front()=arena.back()=12345;
#ifdef PLATEAU_EXPLICIT_INIT
    if(p_init_core(d,arena.data()+1,size)!=size)return 0;
#else
    if(p_bind_core(d,arena.data()+1,size)!=size)return 0;
#endif
#endif
    d->clear();d->setTimeScale(p[0]);d->setPreDelay(p[1]);d->setDecay(p[2]);
    d->setTankModSpeed(p[3]);d->setTankModDepth(p[4]);d->setTankModShape(p[5]);
    d->enableInputDiffusion(p[6]>0);d->setTankDiffusion(p[6]*.7);
    d->setInputFilterLowCutoffPitch(p[7]);d->setInputFilterHighCutoffPitch(p[8]);
    d->setTankFilterLowCutFrequency(p[9]);d->setTankFilterHighCutFrequency(p[10]);
    for(unsigned i=0;i<frames;++i){d->process(input[2*i],input[2*i+1]);
        output[2*i]=d->getLeftOutput();output[2*i+1]=d->getRightOutput();}
#ifdef PL_DERIVED
    if(arena.front()!=12345 || arena.back()!=12345)return 0;
    return size;
#else
    return count;
#endif
}
#ifdef PL_SANITIZE_MAIN
#include <cmath>
int main(){
    const unsigned frames=192000;
    std::vector<float> input(frames*2),output(frames*2);
    for(unsigned i=0;i<frames*2;++i)input[i]=.001f*std::sin(.137f*i);
    for(float size:{.01f,1.0075f,4.0f})for(float shape:{.001f,.999f}){
        const float parameters[]={size,.5f,.95f,100.5f,16,shape,1,2,8,1,9};
        if(!plateau_render(input.data(),output.data(),frames,parameters))return 1;
        for(auto sample:output)if(!std::isfinite(sample))return 2;
    }
}
#endif
