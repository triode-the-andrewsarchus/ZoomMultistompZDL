/* Generated TI C++ inline syntax adaptation. */
/* Small-effect MS Plus adapter, built by Stomphacks. No delay-memory access.
 * The init guard lives AFTER state_bytes; manifest must fit <=188 user bytes.
 * Always snapshot coefficients, validate locals, then use only those locals.
 */
#ifndef ZDL_MSPLUS_COMPAT_H
#define ZDL_MSPLUS_COMPAT_H
#include <stdint.h>
#include "sh_params.h"

static __attribute__((always_inline)) inline int mp_ready(void **instance, float fade)
{
    return ((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] == SH_STATE_GUARD
        && fade >= 0.0f && fade <= 1.0f;
}

static __attribute__((always_inline)) inline int mp_normalized(float value)
{
    return value >= 0.0f && value <= 1.0f;
}

static __attribute__((always_inline)) inline void mp_silence(float *bus)
{
    int i;
    for (i = 0; i < SH_FRAMES * 2; ++i) bus[i] = 0.0f;
}

static __attribute__((always_inline)) inline float mp_input(float sample)
{
    return sample > -2.0f && sample < 2.0f ? sample : 0.0f;
}

static __attribute__((always_inline)) inline float mp_output(float dry, float wet, float fade)
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
static __attribute__((always_inline)) inline uintptr_t mp_arena_state(void **instance, uintptr_t required)
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

/* Keep integer/control state from being interpreted as audio after an effect
 * change. Stock CloneCho reuses delay memory without clearing it in _init.
 * Each raw 32-bit word is saved as two 16-bit integers in separate words:
 * both storage words are tiny finite float bit patterns. The raw header is
 * zero between callbacks. Audio rings outside the header are not moved.
 * No float conversion is used: every bit, including integer -1, round-trips.
 */
#ifndef MSPLUS_ARENA_STATE_H
#define MSPLUS_ARENA_STATE_H
#ifdef __TI_COMPILER_VERSION__


#endif
static __attribute__((always_inline)) inline void mp_unpack_header(uintptr_t base, uintptr_t packed, unsigned int bytes)
{
    unsigned char *raw = (unsigned char *)base;
    const uint32_t *saved = (const uint32_t *)packed;
    unsigned int i;
    for (i = 0; i < bytes / 4; ++i) {
        uint32_t lo = saved[2*i], hi = saved[2*i+1];
        raw[4*i] = (unsigned char)lo;
        raw[4*i+1] = (unsigned char)(lo >> 8);
        raw[4*i+2] = (unsigned char)hi;
        raw[4*i+3] = (unsigned char)(hi >> 8);
    }
}

static __attribute__((always_inline)) inline void mp_pack_header(uintptr_t base, uintptr_t packed, unsigned int bytes)
{
    unsigned char *raw = (unsigned char *)base;
    uint32_t *saved = (uint32_t *)packed;
    unsigned int i;
    for (i = 0; i < bytes / 4; ++i) {
        saved[2*i] = (uint32_t)raw[4*i] | ((uint32_t)raw[4*i+1] << 8);
        saved[2*i+1] = (uint32_t)raw[4*i+2] | ((uint32_t)raw[4*i+3] << 8);
        raw[4*i] = raw[4*i+1] = raw[4*i+2] = raw[4*i+3] = 0;
    }
}
#endif
