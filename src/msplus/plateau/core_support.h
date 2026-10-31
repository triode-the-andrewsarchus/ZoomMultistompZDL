/* Bounded arena delay and inline arithmetic for the GPL Plateau adaptation.
 * Delay/allpass indexing retains the original write/read ordering. */
#ifndef MSPLUS_PLATEAU_CORE_SUPPORT_H
#define MSPLUS_PLATEAU_CORE_SUPPORT_H
#include <stdint.h>
#ifdef __TI_COMPILER_VERSION__
#include <c6x.h>
#endif
#define PL_INLINE __attribute__((always_inline)) inline
static PL_INLINE float p_recip(float x) {
#ifdef __TI_COMPILER_VERSION__
    float y=_rcpsp(x); y*=2.0f-x*y;y*=2.0f-x*y;return y;
#else
    return 1.0f/x;
#endif
}
static PL_INLINE float p_exp2(float x) {
    int n=(int)x;if((float)n>x)--n;
    float f=x-(float)n;
    union {uint32_t u;float f;} v;v.u=(uint32_t)(127+n)<<23;
    return v.f*(1.0f+f*(.69314718056f+f*(.24022650696f+f*(.05550410866f+
        f*(.009618129108f+f*(.001333355815f+f*(.000154035304f+f*.000015252734f)))))));
}
static PL_INLINE float p_expf(float x){return p_exp2(x*1.442695040889f);}
static PL_INLINE float p_sqrt(float x){
#ifdef __TI_COMPILER_VERSION__
    float y=_rsqrsp(x);y*=1.5f-.5f*x*y*y;y*=1.5f-.5f*x*y*y;return x*y;
#else
    return __builtin_sqrtf(x);
#endif
}
/* Positive finite domain only; the caller applies the original dB floor. */
static PL_INLINE float p_log2(float x){
    union {uint32_t u;float f;} v;v.f=x;
    int exponent=(int)(v.u>>23)-127;v.u=(v.u&0x7fffffu)|0x3f800000u;
    float y=(v.f-1)*p_recip(v.f+1),z=y*y;
    return (float)exponent+2.885390081778f*y*(1+z*(1.0f/3+z*(1.0f/5+
        z*(1.0f/7+z*(1.0f/9+z*(1.0f/11))))));
}
class InterpDelay {
public:
#ifdef PLATEAU_EXPLICIT_INIT
    float input,output;
    float *data;
    int l,w,t;
    float f;
    PL_INLINE InterpDelay(unsigned maxLength=512,float delay=0):input(0),output(0),data(nullptr),l(0),w(0),t(0),f(0){}
#else
    float input=0,output=0;
    float *data=nullptr;
    int l=512,w=0,t=0;
    float f=0;
    PL_INLINE InterpDelay(unsigned maxLength=512,float delay=0):l((int)maxLength){setDelayTime(delay);}
#endif
    PL_INLINE void process(){
        data[w]=input;
        int r=w-t;if(r<0)r+=l;
        if(++w>=l)w=0;
        int upper=r-1;if(upper<0)upper+=l;
        output=data[r]+f*(data[upper]-data[r]);
    }
    PL_INLINE float tap(const int &i){int j=w-i;if(j<0)j+=l;return data[j];}
    PL_INLINE void setDelayTime(float delay){
        if(delay>=(float)l)delay=(float)(l-1);
        if(delay<0)delay=0;
        t=(int)delay;f=delay-(float)t;
    }
    PL_INLINE void clear(){
        for(int i=0;i<l;++i)data[i]=0;
        input=output=0;
    }
};
#endif
