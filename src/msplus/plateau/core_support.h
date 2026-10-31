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
class InterpDelay {
public:
    float input=0,output=0;
    float *data=nullptr;
    int l=512,w=0,t=0;
    float f=0;
    PL_INLINE InterpDelay(unsigned maxLength=512,float delay=0):l((int)maxLength){setDelayTime(delay);}
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
