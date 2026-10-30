/* Plus WaveFold: one to five cascaded sine-folding cells at 4x sample rate.
 * Original DSP for this port, not the Matujuice parallel threshold model.
 * RMS matching reuses Matujuice's MIT inverse-square-root method
 * (Luca Matturro; ../MATUJUICE-LICENSE), with zero initial gain.
 */
#include "../common/force_inline.h"
#include <stddef.h>
#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(wf_sinefold)
#pragma FUNC_ALWAYS_INLINE(wf_cascade)
#pragma FUNC_ALWAYS_INLINE(wf_filter)
#pragma FUNC_ALWAYS_INLINE(wf_rsqrt)
#pragma FUNC_ALWAYS_INLINE(wf_init)
#pragma FUNC_ALWAYS_INLINE(wf_oversample)
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
#define WF_MAGIC 0x57463532u
typedef struct {
    uint32_t magic;
    float drive, bias, tone, level, mix;
    float ein, ewet, comp, dcx, dcy, lp;
    float voiceLow, voiceBlend, pre1, pre2;
    float dry[12];
    float up1[17], up2[17], down2[17], down1[17];
} WfState;

/* sin(pi*x/2): range-reduced, bounded, degree-13 polynomial. Smooth fold
 * knees reduce high harmonics; no libm, divides or unbounded loops. */
static inline float wf_sinefold(float x)
{
    float a = x < 0.0f ? -x : x;
    a -= 4.0f * (float)(int)(a * .25f);
    if (a > 3.0f) a -= 4.0f;
    else if (a > 1.0f) a = 2.0f-a;
    float q = a*a;
    float y = a*(1.5707963268f+q*(-.6459640975f+q*(.07969262625f+q*
        (-.004681754135f+q*(.0001604411848f+q*(-.000003598843235f+q*.00000005692172922f))))));
    return x < 0.0f ? -y : y;
}
static inline float wf_cascade(float x, float gain, float bias, int stages)
{
    float center = wf_sinefold(bias);
    int stage;
    for (stage = 0; stage < stages; ++stage) {
        float sign = (stage & 1) ? -1.0f : 1.0f;
        x = wf_sinefold(x*gain+sign*bias)-sign*center;
    }
    return x;
}
/* Unity-DC, 17-tap Kaiser half-band FIR. Four filters form
 * 2x -> 4x -> 2x -> 1x, with total delay of 12 base-rate samples.
 * Literal coefficients avoid DSP constant-pool relocations. */
static inline float wf_filter(float *history, float sample)
{
    int i;
    for (i = 16; i > 0; --i) history[i] = history[i-1];
    history[0] = sample;
    return .5f*history[8]-.0010771966802f*(history[1]+history[15])
        +.0125207812063f*(history[3]+history[13])
        -.0615394033947f*(history[5]+history[11])
        +.3000958188686f*(history[7]+history[9]);
}
static inline float wf_rsqrt(float x)
{
    union { float f; uint32_t u; } c;
    c.f = x; c.u = 0x5f3759dfu-(c.u >> 1);
    float y = c.f, h = .5f*x;
    y *= 1.5f-h*y*y;
    y *= 1.5f-h*y*y;
    y *= 1.5f-h*y*y;
    return y;
}
static inline void wf_init(WfState *s, const float *params)
{
    volatile float *words = (volatile float *)s;
    unsigned int i;
    for (i = 0; i < sizeof(*s)/sizeof(float); ++i) words[i] = 0.0f;
    s->drive = params[5]; s->bias = params[6]; s->tone = params[8];
    s->level = params[9]; s->mix = params[10];
    s->voiceLow = params[7] < .25f ? 1.0f : 0.0f;
    s->voiceBlend = params[7] > .75f ? 1.0f : 0.0f;
    s->magic = WF_MAGIC;
}
static inline float wf_oversample(WfState *s, float input, float gain, float bias, int stages)
{
    float result = 0.0f;
    int outer, inner;
    for (outer = 0; outer < 2; ++outer) {
        float up = 2.0f*wf_filter(s->up1, outer == 0 ? input : 0.0f);
        float middle = 0.0f;
        for (inner = 0; inner < 2; ++inner) {
            float high = 2.0f*wf_filter(s->up2, inner == 0 ? up : 0.0f);
            float low = wf_filter(s->down2, wf_cascade(high, gain, bias, stages));
            if (inner == 0) middle = low;
        }
        float low = wf_filter(s->down1, middle);
        if (outer == 0) result = low;
    }
    return result;
}
static inline int mp_half(WfState *s, const float *params, float *buffer)
{
    int i, j;
    if (params[0] < .5f) return 0;
    if (s->magic != WF_MAGIC) wf_init(s, params);
    /* A bounded loop preserves the wrapped, biased cell topology. A single
     * composed polynomial would have degree 13^N plus moving wrap boundaries.
     * Fewer cells need more input trim to retain a useful Drive range. */
    int stages = 1+(int)(4.0f*params[11]+.5f);
    float stageTrim = (float)(1u << (5-stages));
    for (i = 0; i < 8; ++i) {
        s->drive += .003f*(params[5]-s->drive);
        s->bias += .003f*(params[6]-s->bias);
        s->tone += .003f*(params[8]-s->tone);
        s->level += .003f*(params[9]-s->level);
        s->mix += .003f*(params[10]-s->mix);
        s->voiceLow += .003f*((params[7] < .25f ? 1.0f : 0.0f)-s->voiceLow);
        s->voiceBlend += .003f*((params[7] > .75f ? 1.0f : 0.0f)-s->voiceBlend);
        float input = buffer[i], dry = s->dry[11];
        /* ~900 Hz two-pole input filtering; generates new harmonics AFTER
         * removing high fundamentals. Warm continuously for quiet switching. */
        s->pre1 += .12f*(input-s->pre1);
        s->pre2 += .12f*(s->pre1-s->pre2);
        float voiced = input+s->voiceLow*(s->pre2-input);
        for (j = 11; j > 0; --j) s->dry[j] = s->dry[j-1];
        s->dry[0] = input;
        float preamp = 2.0f+126.0f*s->drive*s->drive;
        float gain = .6366197724f+2.1633802276f*s->drive;
        float bias = s->bias-.5f;
        float wet = wf_oversample(s, voiced*preamp*stageTrim, gain, bias, stages);
        float dc = wet-s->dcx+.9993f*s->dcy;
        s->dcx = wet; s->dcy = dc;
        s->lp += (.03f+.97f*s->tone*s->tone)*(dc-s->lp);
        s->ein += .0003f*(dry*dry-s->ein);
        s->ewet += .0003f*(s->lp*s->lp-s->ewet);
        if (s->ein > 1e-12f && s->ewet > 1e-12f) {
            float target = s->ein*wf_rsqrt(s->ein*s->ewet);
            if (target > 8.0f) target = 8.0f;
            s->comp += .003f*(target-s->comp);
        }
        wet = s->lp*s->comp;
        /* Independent parallel-clean VOICE, before overall Level and Mix. */
        wet += .45f*s->voiceBlend*(dry-wet);
        wet *= 2.0f*s->level;
        buffer[i] = dry+s->mix*(wet-dry);
    }
    return 1;
}
static inline void mp_raw_controls(float *params, const float *values)
{
    int i;
    for (i = 0; i < 7; ++i) params[5+i] = values[i];
}
#define MJ_STATE_TYPE WfState
#define MJ_PARAM_COUNT 7
#define MJ_PACKED_HEADER_BYTES offsetof(WfState, dry)
#include "../common/matujuice_kernel.h"
