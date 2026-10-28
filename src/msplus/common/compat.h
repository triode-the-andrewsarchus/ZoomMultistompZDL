/* Small-effect MS Plus adapter, built by Stomphacks. No delay-memory access.
 * The init guard lives AFTER state_bytes; manifest must fit <=188 user bytes.
 * Always snapshot coefficients, validate locals, then use only those locals.
 */
#ifndef ZDL_MSPLUS_COMPAT_H
#define ZDL_MSPLUS_COMPAT_H
#include <stdint.h>
#include "sh_params.h"

static inline int mp_ready(void **instance, float fade)
{
    return ((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] == SH_STATE_GUARD
        && fade >= 0.0f && fade <= 1.0f;
}

static inline int mp_normalized(float value)
{
    return value >= 0.0f && value <= 1.0f;
}

static inline void mp_silence(float *bus)
{
    int i;
    for (i = 0; i < SH_FRAMES * 2; ++i) bus[i] = 0.0f;
}

static inline float mp_input(float sample)
{
    return sample > -2.0f && sample < 2.0f ? sample : 0.0f;
}

static inline float mp_output(float dry, float wet, float fade)
{
    float out = dry + fade * (wet - dry);
    /* Comparison also rejects NaN and infinity. Never bypass this clamp. */
    if (!(out > -2.0f && out < 2.0f)) out = 0.0f;
    return out;
}
#endif
