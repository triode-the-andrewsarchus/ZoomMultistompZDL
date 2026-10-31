/* OFFLINE INTEGRATION ONLY. Incomplete development fixture; do not install. */
#define PLATEAU_EXPLICIT_INIT
#include <new>
#include <stddef.h>
extern "C" {
#include "../cpp_compat.h"
}

#include "../core_bind.h"
#include "../cpp_resample.h"
struct State{ PL_INLINE State(){} uint32_t magic,clear; Dattorro reverb{32000,16,4};PlateauSRC src;float history[144261];};
#define HEADER offsetof(State,history)
#define PACKED ((sizeof(State)+7u)&~(uintptr_t)7u)
extern "C" void SH_AUDIO_FN(void **instance,void **ctx){
 const float *c=(const float*)instance[1];float *b=(float*)ctx[1],f=c[0],m=c[5];
 if(!mp_ready(instance,f)||!mp_normalized(m)){mp_silence(b);return;}
 uint32_t *small=(uint32_t*)instance[2],old=small[0];
 uintptr_t base=mp_arena_state(instance,PACKED+2*HEADER);if(!base){mp_silence(b);return;}
 if(old==(uint32_t)base&&small[1]==1)mp_unpack_header(base,base+PACKED,HEADER);
 State *s=(State*)base;unsigned i;
 if(s->magic!=0x504c3031u){volatile uint32_t *p=(volatile uint32_t*)s;for(i=0;i<HEADER/4;++i)p[i]=0;
 new(s)State;s->clear=0;
 for(unsigned channel=0;channel<2;++channel)for(unsigned j=0;j<128;++j){
   ((volatile float*)s->src.input[channel])[j]=0;((volatile float*)s->src.output[channel])[j]=0;
 }
 s->magic=0x504c3031u;s->src.phase=121;s->src.inwrite=s->src.outwrite=63;
 if(!p_init_core(&s->reverb,s->history,144261)){mp_silence(b);goto packed_exit;}
 }
 for(i=0;i<1024&&s->clear<144261;++i)((volatile float*)s->history)[s->clear++]=0;
 for(i=0;i<SH_FRAMES;++i){float a=mp_input(b[i]),d=mp_input(b[i+SH_CH_B_OFFSET]),l=a,r=d;
 if(s->clear==144261){
 if(ps_push(&s->src,a,d)){ps_down(&s->src,&l,&r);s->reverb.process(l,r);ps_store(&s->src,s->reverb.getLeftOutput(),s->reverb.getRightOutput());}
 ps_up(&s->src,&l,&r);}
 b[i]=mp_output(a,a+m*(l-a),f);b[i+SH_CH_B_OFFSET]=mp_output(d,d+m*(r-d),f);}
 packed_exit:
 mp_pack_header(base,base+PACKED,HEADER);small[1]=1;
}
