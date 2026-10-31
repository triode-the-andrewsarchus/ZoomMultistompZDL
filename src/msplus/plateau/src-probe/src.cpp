extern "C" {
#include "../cpp_compat.h"
}
#include "../cpp_resample.h"
#ifdef PLATEAU_PROBE_OUTPUT
#include "../output.h"
#endif
typedef struct {uint32_t magic;PlateauSRC src;
#ifdef PLATEAU_PROBE_OUTPUT
PlateauOutput output;unsigned clear;PlateauOutputMemory memory;
#endif
} State;
#ifdef PLATEAU_PROBE_OUTPUT
#include <stddef.h>
#define PROBE_HEADER offsetof(State,memory)
#else
#define PROBE_HEADER sizeof(State)
#endif
extern "C" void SH_AUDIO_FN(void **instance,void **ctx){
 const float *c=(const float*)instance[1];float *b=(float*)ctx[1],f=c[0],m=c[5];
 if(!mp_ready(instance,f)||!mp_normalized(m)){mp_silence(b);return;}
 uint32_t *small=(uint32_t*)instance[2],old=small[0];uintptr_t offset=(sizeof(State)+7u)&~(uintptr_t)7u;
 uintptr_t base=mp_arena_state(instance,offset+2*PROBE_HEADER);if(!base){mp_silence(b);return;}
 if(old==(uint32_t)base&&small[1]==1)mp_unpack_header(base,base+offset,PROBE_HEADER);
 State *s=(State*)base;unsigned i;
 if(s->magic!=0x504c3031u){volatile uint32_t *p=(volatile uint32_t*)s;for(i=0;i<PROBE_HEADER/4;++i)p[i]=0;s->magic=0x504c3031u;s->src.phase=121;s->src.inwrite=s->src.outwrite=63;
#ifdef PLATEAU_PROBE_OUTPUT
po_output_bind(&s->output,&s->memory);s->clear=0;
#endif
}
#ifdef PLATEAU_PROBE_OUTPUT
s->clear=po_output_step(&s->memory,s->clear,1024);
#endif
 for(i=0;i<SH_FRAMES;++i){float a=mp_input(b[i]),d=mp_input(b[i+SH_CH_B_OFFSET]),l,r;
 if(ps_push(&s->src,a,d)){ps_down(&s->src,&l,&r);
#ifdef PLATEAU_PROBE_OUTPUT
if(s->clear==PO_OUTPUT_WORDS)po_process(&s->output,&l,&r,1,0);else l=r=0;
#endif
ps_store(&s->src,l,r);}
 ps_up(&s->src,&l,&r);b[i]=mp_output(a,l*m,f);b[i+SH_CH_B_OFFSET]=mp_output(d,r*m,f);}
 for(i=0;i<SH_FRAMES*2;++i){if(b[i]>.02f)b[i]=.02f;if(b[i]<-.02f)b[i]=-.02f;}
 mp_pack_header(base,base+offset,PROBE_HEADER);small[1]=1;
}
