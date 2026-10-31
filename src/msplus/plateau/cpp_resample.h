/* Generated TI C++ inline syntax adaptation. */
/* Causal 44.1 <-> 32 kHz stereo SRC. Caller owns/initializes this state and
 * checks its phase/write bounds before use. Tables are readonly; no calls,
 * allocation, writable globals or firmware services. */
#ifndef MSPLUS_PLATEAU_RESAMPLE_H
#define MSPLUS_PLATEAU_RESAMPLE_H
#include <stdint.h>
#include "resample_coeffs.h"
#ifdef __TI_COMPILER_VERSION__





#endif
typedef struct {
    uint32_t phase, inwrite, outwrite;
    float input[2][128], output[2][128];
} PlateauSRC;
static __attribute__((always_inline)) inline int ps_push(PlateauSRC *s,float left,float right) {
    s->inwrite=(s->inwrite+1u)&63u;
    s->input[0][s->inwrite]=s->input[0][s->inwrite+64]=left;
    s->input[1][s->inwrite]=s->input[1][s->inwrite+64]=right;
    s->phase+=320;
    if(s->phase>=441){s->phase-=441;return 1;}
    return 0;
}
static __attribute__((always_inline)) inline void ps_store(PlateauSRC *s,float left,float right) {
    s->outwrite=(s->outwrite+1u)&63u;
    s->output[0][s->outwrite]=s->output[0][s->outwrite+64]=left;
    s->output[1][s->outwrite]=s->output[1][s->outwrite+64]=right;
}
static __attribute__((always_inline)) inline void ps_filter(const float history[2][128],unsigned write,
                            const float table[33][64],float phase,float *left,float *right) {
    float position=phase*32.0f;
    int index=(int)position;
    if(index>31)index=31;
    float fraction=position-(float)index;
    float a=0,b=0;unsigned k;
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for(k=0;k<64;++k) {
        float coefficient=table[index][k]+fraction*(table[index+1][k]-table[index][k]);
        a+=coefficient*history[0][write+64-k];
        b+=coefficient*history[1][write+64-k];
    }
    *left=a;*right=b;
}
static __attribute__((always_inline)) inline void ps_down(const PlateauSRC *s,float *left,float *right) {
    ps_filter(s->input,s->inwrite,plateau_down,(float)s->phase*(1.0f/320.0f),left,right);
}
static __attribute__((always_inline)) inline void ps_up(const PlateauSRC *s,float *left,float *right) {
    ps_filter(s->output,s->outwrite,plateau_up,1.0f-(float)s->phase*(1.0f/441.0f),left,right);
}
#endif
