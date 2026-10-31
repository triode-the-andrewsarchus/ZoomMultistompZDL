/* Native bridge for the exact control implementation used on target. */
#define PLATEAU_EXPLICIT_INIT
#include <new>
#include <vector>
#include <cstring>
#include "controls.h"
extern "C" unsigned plateau_controls_trace(const float *rows,float *trace,unsigned count){
    alignas(Dattorro) unsigned char storage[sizeof(Dattorro)];
    std::memset(storage,0xa5,sizeof(storage));
    Dattorro *d=new(storage) Dattorro(32000,16,4);
    std::vector<float> arena(144261);
    if(p_init_core(d,arena.data(),144261,false)!=144261)return 0;
    PlateauControls s;pc_init(&s);
    for(unsigned block=0;block<count;++block){
        unsigned clear=pc_block(&s,d,rows+10*block,12);
        float *out=trace+32*block;
        out[0]=d->tank.timeScale;out[1]=(d->preDelay.t+d->preDelay.f)/32000;
        out[2]=d->tank.decayParam;out[3]=d->tank.modDepth;
        out[4]=d->inputHighCut;out[5]=d->inputLowCut;out[6]=d->diffuseInput;
        out[7]=2*s.smooth[5];out[8]=d->tank.frozen?1:0;out[9]=(float)clear;
        out[10]=s.smooth[0];out[11]=s.lockedDepth;
        for(unsigned i=0;i<9;++i){out[12+i]=s.advanced[i];out[21+i]=s.target[i];}
    }
    return 1;
}
