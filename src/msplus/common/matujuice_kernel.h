/* Shared Plus entry for the pristine Matujuice v1.5 mono DSP cores.
 * Include after defining MJ_STATE_TYPE, MJ_PARAM_COUNT, mp_half and
 * mp_raw_controls. Two eight-frame calls preserve source clock cadence.
 * Bus B is the physical left input on this MS-70CDR+ rig.
 */
#include <stddef.h>
#ifdef MP_RAW_STATE_REFERENCE
#ifdef __TI_COMPILER_VERSION__
#error Raw arena state is only supported by the native reference host
#endif
#undef MJ_PACKED_HEADER_BYTES
#endif
#ifndef MJ_OWN_BYPASS
#define MJ_OWN_BYPASS 0
#endif
#ifdef MJ_PACKED_HEADER_BYTES
#include "arena_state.h"
#ifndef MJ_HEADER_CODEC
#define MJ_HEADER_CODEC(operation, base, packed) \
    operation(base, packed, MJ_PACKED_HEADER_BYTES)
#endif
typedef char mp_header_fits[(MJ_PACKED_HEADER_BYTES <= sizeof(MJ_STATE_TYPE)
                            && MJ_PACKED_HEADER_BYTES % 4 == 0
                            && SH_STATE_GUARD_WORD >= 2) ? 1 : -1];
#endif
void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *bus = (float *)ctx[1];
    float fade = coef[SH_COEFF_BYPASS];
    float values[MJ_PARAM_COUNT];
    int i, half;
    if (!mp_ready(instance, fade)) { mp_silence(bus); return; }
    for (i = 0; i < MJ_PARAM_COUNT; ++i) {
        values[i] = coef[5+i];
        if (!mp_normalized(values[i])) { mp_silence(bus); return; }
    }
#ifdef MJ_PACKED_HEADER_BYTES
    uintptr_t packedOffset = (sizeof(MJ_STATE_TYPE) + 7u) & ~(uintptr_t)7u;
    uint32_t oldBase = ((uint32_t *)instance[2])[0];
    uintptr_t base = mp_arena_state(instance, packedOffset + 2u*MJ_PACKED_HEADER_BYTES);
#else
    uintptr_t base = mp_arena_state(instance, sizeof(MJ_STATE_TYPE));
#endif
    if (!base) { mp_silence(bus); return; }
#ifdef MJ_PACKED_HEADER_BYTES
    uint32_t *small = (uint32_t *)instance[2];
    if (oldBase == (uint32_t)base && small[1] == 1u)
        MJ_HEADER_CODEC(mp_unpack_header, base, base + packedOffset);
#endif
    float params[15];
    params[0] = fade;
    mp_raw_controls(params, values);
#ifdef __TI_COMPILER_VERSION__
#pragma UNROLL(1)
#endif
    for (half = 0; half < 2; ++half) {
        float mono[8];
        for (i = 0; i < 8; ++i)
            mono[i] = mp_input(bus[SH_CH_B_OFFSET + half*8+i]);
        int processed = mp_half((MJ_STATE_TYPE *)base, params, mono);
        for (i = 0; i < 8; ++i) {
            int at = half*8+i;
            float dryA = mp_input(bus[at]), dryB = mp_input(bus[at+SH_CH_B_OFFSET]);
            float outputFade = MJ_OWN_BYPASS ? 1.0f : fade;
            bus[at] = mp_output(dryA, processed ? mono[i] : dryA, outputFade);
            bus[at+SH_CH_B_OFFSET] = mp_output(dryB, processed ? mono[i] : dryB, outputFade);
        }
    }
#ifdef MJ_PACKED_HEADER_BYTES
    MJ_HEADER_CODEC(mp_pack_header, base, base + packedOffset);
    small[1] = 1u;
#endif
}
