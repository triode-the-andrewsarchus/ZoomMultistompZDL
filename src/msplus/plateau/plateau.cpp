/* Plateau/Campestria plate reverb. Experimental: never save in a patch. */
#define PLATEAU_EXPLICIT_INIT
#include <new>
#include <stddef.h>
extern "C" {
#include "cpp_compat.h"
}
#include "core_bind.h"
#include "cpp_resample.h"
#include "output.h"
#include "controls.h"
struct State {
    PL_INLINE State(){}
    uint32_t magic,clear,outclear,resetPhase;
    float clearGain;
    Dattorro reverb{32000,16,4};
    PlateauSRC src;
    PlateauOutput output;
    PlateauControls controls;
    float history[144261];
    PlateauOutputMemory outputmemory;
};
#define HEADER offsetof(State,history)
#define PACKED ((sizeof(State)+7u)&~(uintptr_t)7u)
static_assert(PACKED+2*HEADER<=705600u,"Plateau arena exceeds verified standalone grant");
static PL_INLINE int construct(State *s){
    new(s)State;s->clear=s->outclear=0;s->resetPhase=2;s->clearGain=0;
    for(unsigned channel=0;channel<2;++channel)for(unsigned j=0;j<128;++j){
        ((volatile float*)s->src.input[channel])[j]=0;((volatile float*)s->src.output[channel])[j]=0;
    }
    s->src.phase=121;s->src.inwrite=s->src.outwrite=63;
    po_output_bind(&s->output,&s->outputmemory);pc_init(&s->controls);
    s->magic=0x504c3032u;
    return p_init_core(&s->reverb,s->history,144261,false)==144261;
}
static PL_INLINE void prepare(State *s,const float knobs[10]){
    unsigned frames=s->src.phase>=172?12:11;
    if(pc_block(&s->controls,&s->reverb,knobs,frames)&&s->resetPhase!=2)s->resetPhase=1;
    if(s->resetPhase==2){
        for(unsigned i=0;i<1024&&s->clear<144261;++i)((volatile float*)s->history)[s->clear++]=0;
        if(s->clear==144261&&s->outclear==PO_OUTPUT_WORDS){p_clear_signals(&s->reverb);s->resetPhase=3;}
    }
    if(s->outclear<PO_OUTPUT_WORDS)s->outclear=po_output_step(&s->outputmemory,s->outclear,1024);
}
static PL_INLINE void internal_frame(State *s,float *left,float *right,uint32_t *faults){
    float a=po_clip(*left,1),b=po_clip(*right,1),l=0,r=0;
    if(s->resetPhase==1){
        s->clearGain*=.99f;
        if(s->clearGain<.0001f){s->clearGain=0;s->resetPhase=2;s->clear=0;}
    }else if(s->resetPhase==3){
        s->clearGain=.01f+.99f*s->clearGain;
        if(s->clearGain>.9999f){s->clearGain=1;s->resetPhase=0;}
    }
    if(s->resetPhase!=2){
        float input=.12589254f*(1+7*s->controls.advanced[PC_INPUT])*s->clearGain;
        s->reverb.process(a*input,b*input);l=s->reverb.getLeftOutput();r=s->reverb.getRightOutput();
        if(!(l>-64&&l<64&&r>-64&&r<64)){
            ++*faults;s->resetPhase=2;s->clear=0;s->clearGain=0;l=r=0;
        }
    }
    float mix=s->controls.smooth[0];
    l=a*(1-mix)+l*(mix*s->clearGain);r=b*(1-mix)+r*(mix*s->clearGain);
    po_process(&s->output,&l,&r,2*s->controls.smooth[5],s->controls.advanced[PC_LIMIT]);
    *left=l;*right=r;
}
extern "C" void SH_AUDIO_FN(void **instance,void **ctx){
    const float *coeff=(const float*)instance[1];
    float *bus=(float*)ctx[1],fade=coeff[0],knobs[10];
    if(!mp_ready(instance,fade)){mp_silence(bus);return;}
    for(unsigned i=0;i<10;++i){knobs[i]=coeff[5+i];if(!mp_normalized(knobs[i])){mp_silence(bus);return;}}
    uint32_t *small=(uint32_t*)instance[2],old=small[0];
    uintptr_t base=mp_arena_state(instance,PACKED+2*HEADER);
    if(!base){mp_silence(bus);return;}
    if(old==(uint32_t)base&&small[1]==1)mp_unpack_header(base,base+PACKED,HEADER);
    State *s=(State*)base;
    if(s->magic!=0x504c3032u){small[2]=0;if(!construct(s)){mp_silence(bus);goto packed_exit;}}
    if(s->clear>144261||s->outclear>PO_OUTPUT_WORDS||s->resetPhase>3||s->src.phase>=441||s->src.inwrite>=64||s->src.outwrite>=64){
        ++small[2];mp_silence(bus);goto packed_exit;
    }
    prepare(s,knobs);
    for(unsigned i=0;i<SH_FRAMES;++i){
        float a=mp_input(bus[i]),b=mp_input(bus[i+SH_CH_B_OFFSET]),l=a,r=b;
        if(s->outclear==PO_OUTPUT_WORDS){
            if(ps_push(&s->src,a,b)){ps_down(&s->src,&l,&r);internal_frame(s,&l,&r,&small[2]);ps_store(&s->src,l,r);}
            ps_up(&s->src,&l,&r);
        }
        bus[i]=mp_output(a,l,fade);bus[i+SH_CH_B_OFFSET]=mp_output(b,r,fade);
    }
packed_exit:
    mp_pack_header(base,base+PACKED,HEADER);small[1]=1;
}
