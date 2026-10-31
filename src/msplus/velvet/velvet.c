/* Dynamic Velvet Decorrelator: derived from 115dkk's MIT processor.cpp,
 * a391a12a0b96b190a05cd7cefa25becf4f31660c; copyright 2026 115dkk.
 * See LICENSE. Float32, fixed arena, stereo/mono routing and cooperative
 * generation are Plus adaptations. Three banks keep renewal off the audio
 * deadline without delaying the original two-bank equal-power transition.
 */
#include "../common/force_inline.h"
#include "../common/arena_state.h"
#include <stddef.h>
#ifdef __TI_COMPILER_VERSION__
#include <c6x.h>
#pragma FUNC_ALWAYS_INLINE(vn_recip)
#pragma FUNC_ALWAYS_INLINE(vn_rsqrt)
#pragma FUNC_ALWAYS_INLINE(vn_exp2)
#pragma FUNC_ALWAYS_INLINE(vn_sin)
#pragma FUNC_ALWAYS_INLINE(vn_random)
#pragma FUNC_ALWAYS_INLINE(vn_seed)
#pragma FUNC_ALWAYS_INLINE(vn_start_bank)
#pragma FUNC_ALWAYS_INLINE(vn_generate)
#pragma FUNC_ALWAYS_INLINE(vn_convolve)
#pragma FUNC_ALWAYS_INLINE(vn_init)
#endif
#define VN_RING 4432
#define VN_TAPS 402
#define VN_MAGIC 0x564e3031u
typedef struct { uint32_t delay; float gain; } VnTap;
typedef struct {
    uint32_t magic, clear, stage, write, active, pending, spare;
    uint32_t ready, generation, until, position, refresh, transition, crossfading;
    uint32_t length, count, jobBank, jobChannel, jobIndex, normalizing, previous;
    uint64_t random;
    float controls[6], energy, scale, mix;
    float ring[2][VN_RING*2];
    VnTap taps[3][2][VN_TAPS];
} VnState;
#define VN_HEADER offsetof(VnState, ring)
#define VN_PACKED ((sizeof(VnState)+7u)&~(uintptr_t)7u)
#define VN_REQUIRED (VN_PACKED+2u*VN_HEADER)
static inline float vn_recip(float x) {
#ifdef __TI_COMPILER_VERSION__
    float y = _rcpsp(x);
    y *= 2.0f-x*y; y *= 2.0f-x*y; return y;
#else
    return 1.0f/x;
#endif
}
static inline float vn_rsqrt(float x) {
    union { uint32_t u; float f; } v;
    v.f=x; v.u=0x5f3759dfu-(v.u>>1);
    float y=v.f, h=.5f*x;
    y*=1.5f-h*y*y; y*=1.5f-h*y*y; y*=1.5f-h*y*y;
    return y;
}
/* 2^x, x in [-20,0], seventh-order fractional Taylor approximation. */
static inline float vn_exp2(float x) {
    int n=(int)x; if ((float)n>x) --n;
    float f=x-(float)n;
    union { uint32_t u; float f; } v; v.u=(uint32_t)(127+n)<<23;
    return v.f*(1.0f+f*(.69314718056f+f*(.24022650696f+f*(.05550410866f+
        f*(.009618129108f+f*(.001333355815f+f*(.000154035304f+f*.000015252734f)))))));
}
/* sin(pi*x/2), x in [0,1], no per-sample libm or table access. */
static inline float vn_sin(float x) {
    float q=x*x;
    return x*(1.5707963268f+q*(-.6459640975f+q*(.07969262625f+
        q*(-.004681754135f+q*(.0001604411848f-q*.000003598843235f)))));
}
static inline uint64_t vn_random(uint64_t *state) {
    uint64_t z=(*state+=UINT64_C(0x9e3779b97f4a7c15));
    z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);
    z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);
    return z^(z>>31);
}
static inline uint64_t vn_seed(uint32_t seed, uint32_t channel, uint32_t generation) {
    uint64_t state=(uint64_t)seed ^ ((uint64_t)(channel+1)*UINT64_C(0xd6e8feb86659fd93))
        ^ ((uint64_t)(generation+1)*UINT64_C(0xa5a3564e27f8862f));
    return vn_random(&state);
}
static inline void vn_start_bank(VnState *s, unsigned bank, unsigned generation) {
    s->jobBank=bank; s->jobChannel=0; s->jobIndex=0; s->normalizing=0;
    s->previous=0; s->energy=0;
    s->random=vn_seed(2050083136u+(unsigned)(int)s->controls[5],0,generation);
}
/* Eight new taps OR 32 normalizations per callback, one channel at a time.
 * Even at 400 taps the future stereo bank finishes within 47 ms, below the
 * minimum 100 ms between finish events. Initial three banks are precomputed.
 */
static inline int vn_generate(VnState *s, unsigned generation, int initial) {
    unsigned budget=s->normalizing ? 32u : 8u;
    VnTap *taps=s->taps[s->jobBank][s->jobChannel];
    float grid=(float)s->length*vn_recip((float)(s->count-1));
    unsigned i;
    for (i=0; i<budget && s->jobIndex<s->count; ++i) {
        unsigned index=s->jobIndex++;
        if (s->normalizing) taps[index].gain*=s->scale;
        else {
            unsigned delay=0;
            if (index) {
                float uniform=(float)(unsigned)(vn_random(&s->random)>>40)*(1.0f/8388608.0f)-1.0f;
                int proposed=(int)(grid*((float)index+.45f*uniform)+.5f);
                unsigned lower=s->previous+1, upper=s->length-(s->count-1-index);
                delay=proposed<(int)lower ? lower : (unsigned)proposed;
                if (delay>upper) delay=upper;
            }
            s->previous=delay;
            float gain=vn_exp2(-s->controls[4]*(float)delay*vn_recip((float)s->length)*.166096404744f);
            if (index && !(vn_random(&s->random)&1u)) gain=-gain;
            taps[index].delay=delay; taps[index].gain=gain;
            s->energy+=gain*gain;
        }
    }
    if (s->jobIndex==s->count) {
        s->jobIndex=0;
        if (!s->normalizing) { s->scale=vn_rsqrt(s->energy); s->normalizing=1; }
        else if (!s->jobChannel) {
            s->jobChannel=1; s->normalizing=0; s->previous=0; s->energy=0;
            s->random=vn_seed(2050083136u+(unsigned)(int)s->controls[5],1,generation+(initial ? 0u : 1u));
        } else return 1;
    }
    return 0;
}
/* Tap-outer block FIR: reuse a tap for 16 adjacent history samples. Mirrored
 * histories remove per-sample wrap branches and preserve contiguous reads.
 * Capacity exceeds maximum delay by at least a full block, so prewriting the
 * block cannot overwrite any history required by its earliest frame. */
static inline void vn_convolve(VnState *s, unsigned bank, unsigned channel,
                               unsigned write, float * restrict output) {
    const VnTap * restrict taps=s->taps[bank][channel];
    const float * restrict ring=s->ring[channel];
    unsigned i,j;
    for(j=0;j<SH_FRAMES;++j) output[j]=0;
#ifdef __TI_COMPILER_VERSION__
#pragma MUST_ITERATE(2,400,1)
#pragma UNROLL(1)
#endif
    for(i=0;i<s->count;++i) {
        unsigned read=write>=taps[i].delay ? write-taps[i].delay : write+VN_RING-taps[i].delay;
        float gain=taps[i].gain;
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(16)
#endif
        for(j=0;j<SH_FRAMES;++j) output[j]+=gain*ring[read+j];
    }
}
static inline void vn_init(VnState *s, const float *p) {
    volatile uint32_t *words=(volatile uint32_t *)s; unsigned i;
    for (i=0;i<VN_HEADER/4;++i) words[i]=0;
    s->controls[0]=p[1];s->controls[1]=p[2];s->controls[2]=p[4];
    s->controls[3]=p[5];s->controls[4]=p[6]*120.0f;s->controls[5]=(float)(unsigned)(int)(p[7]*1000.0f+.5f);
    float ms=p[1]*100.0f; if (ms<1.0f) ms=1.0f;
    float density=p[2]*4000.0f; if(density<100.0f) density=100.0f;
    s->length=(unsigned)(int)(44.1f*ms+.5f);
    s->count=(unsigned)(int)(ms*.001f*density+.5f);
    if(s->count<2) s->count=2;
    if(s->count>s->length+1) s->count=s->length+1;
    s->refresh=(unsigned)(int)(p[4]*2646000.0f+.5f); if(s->refresh<4410) s->refresh=4410;
    s->transition=(unsigned)(int)(p[5]*44100.0f+.5f); if(s->transition<44) s->transition=44;
    if(s->transition>(unsigned)(int)(.9f*(float)s->refresh)) s->transition=(unsigned)(int)(.9f*(float)s->refresh);
    s->active=0;s->pending=1;s->spare=2;s->generation=2;s->mix=p[0];s->magic=VN_MAGIC;
}
void SH_AUDIO_FN(void **instance, void **ctx) {
    const float *coef=(const float *)instance[1]; float *bus=(float *)ctx[1];
    float fade=coef[0], p[9]; unsigned i;
    if(!mp_ready(instance,fade)) {mp_silence(bus);return;}
    for(i=0;i<9;++i) {p[i]=coef[5+i];if(!mp_normalized(p[i])){mp_silence(bus);return;}}
    uint32_t *small=(uint32_t *)instance[2],old=small[0];
    uintptr_t base=mp_arena_state(instance,VN_REQUIRED);
    if(!base){mp_silence(bus);return;}
    if(old==(uint32_t)base && small[1]==1u) mp_unpack_header(base,base+VN_PACKED,VN_HEADER);
    VnState *s=(VnState *)base;
    if(s->magic!=VN_MAGIC || s->controls[0]!=p[1] || s->controls[1]!=p[2]
        || s->controls[2]!=p[4] || s->controls[3]!=p[5] || s->controls[4]!=p[6]*120.0f
        || s->controls[5]!=(float)(unsigned)(int)(p[7]*1000.0f+.5f)) vn_init(s,p);
    int running=s->stage==4;
    if(s->stage==0) {
        volatile float *data=(volatile float *)s->ring;
        unsigned count=(sizeof(VnState)-VN_HEADER)/4;
        for(i=0;i<256 && s->clear<count;++i) data[s->clear++]=0;
        if(s->clear==count){s->stage=1;vn_start_bank(s,0,0);}
    } else if(s->stage<4) {
        unsigned generation=s->stage==1 ? 0u : (s->stage==2 ? 1u : 2u);
        if(vn_generate(s,generation,s->stage<3)) {
            ++s->stage;
            if(s->stage<4) vn_start_bank(s,s->stage-1,s->stage==2 ? 1u : 2u);
            else {s->ready=1;s->until=s->refresh;s->generation=4;}
        }
    } else if(!s->ready && vn_generate(s,s->generation,0)) {s->ready=1;s->generation+=2;}
    unsigned input=(unsigned)(int)(p[8]*2.0f+.5f);
    float primary[2][SH_FRAMES], secondary[2][SH_FRAMES];
    unsigned firstActive=s->active, write=s->write;
    int needPending=running && (s->crossfading || (p[3]>.5f && s->until<=SH_FRAMES));
    if(running) {
        unsigned at=write;
        for(i=0;i<SH_FRAMES;++i) {
            float a=mp_input(bus[i]),b=mp_input(bus[i+SH_CH_B_OFFSET]);
            float left=input==0 ? b : a, right=input==1 ? a : b;
            s->ring[0][at]=s->ring[0][at+VN_RING]=left;
            s->ring[1][at]=s->ring[1][at+VN_RING]=right;
            if(++at==VN_RING) at=0;
        }
        vn_convolve(s,s->active,0,write,primary[0]);
        vn_convolve(s,s->active,1,write,primary[1]);
        if(needPending) {
            vn_convolve(s,s->pending,0,write,secondary[0]);
            vn_convolve(s,s->pending,1,write,secondary[1]);
        }
        s->write=at;
    }
    for(i=0;i<SH_FRAMES;++i) {
        float a=mp_input(bus[i]), b=mp_input(bus[i+SH_CH_B_OFFSET]);
        /* On this verified rig bus B is physical L, bus A physical R. */
        float dry[2];dry[0]=input==0 ? b : a;dry[1]=input==1 ? a : b;
        s->mix+=.003f*(p[0]-s->mix);
        float wet[2];wet[0]=dry[0];wet[1]=dry[1];
        if(running) {
            float phase=(float)s->position*vn_recip((float)(s->transition-1));
            float oldWeight=s->crossfading ? vn_sin(1.0f-phase) : 1.0f;
            float newWeight=s->crossfading ? vn_sin(phase) : 0.0f;
            unsigned ch;
            for(ch=0;ch<2;++ch) {
                wet[ch]=s->active==firstActive ? primary[ch][i] : secondary[ch][i];
                if(s->crossfading) wet[ch]=oldWeight*wet[ch]+newWeight*secondary[ch][i];
            }
            if(p[3]>.5f) {
                if(s->crossfading) {
                    if(++s->position>=s->transition) {
                        unsigned previous=s->active;s->active=s->pending;s->pending=s->spare;s->spare=previous;
                        s->crossfading=0;s->position=0;s->until=s->refresh-s->transition;
                        s->ready=0;vn_start_bank(s,s->spare,s->generation);
                    }
                } else if(s->until && --s->until==0) {s->crossfading=1;s->position=0;}
            }
        }
        bus[i]=mp_output(a,dry[0]+s->mix*(wet[0]-dry[0]),fade);
        bus[i+SH_CH_B_OFFSET]=mp_output(b,dry[1]+s->mix*(wet[1]-dry[1]),fade);
    }
    mp_pack_header(base,base+VN_PACKED,VN_HEADER);small[1]=1;
}
