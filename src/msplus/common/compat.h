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
/* Stock DELAY_C descriptor semantics, corroborated by read-only telemetry on
 * firmware 1.10: {base, exclusive_end, byte_count}. Only the observed grant
 * range is accepted. Call AFTER mp_ready and coefficient checks. Never alter
 * descriptor fields; reset only the effect-owned header on a fresh instance.
 * Buffered manifests reserve one user word in instance[2] for the base stamp.
 */
static inline uintptr_t mp_arena_state(void **instance, uintptr_t required)
{
    const volatile uintptr_t *desc = (const volatile uintptr_t *)instance[3];
    if (!desc || ((uintptr_t)desc & 3u)) return 0;
    uintptr_t base = desc[0], end = desc[1], span = desc[2];
    if (!base || (base & 7u) || end <= base || span != end - base
        || span > 705600u || required > span) return 0;
    uint32_t *stamp = (uint32_t *)instance[2];
    if (*stamp != (uint32_t)base) {
        *(uint32_t *)base = 0;  /* invalidate only our own legacy state magic */
        *stamp = (uint32_t)base;
    }
    return base;
}
#endif
