/* Read-only descriptor telemetry. Stock DELAY_C uses instance[3] as a
 * three-word {base, end, byte_count} ring descriptor (see research notes).
 * Never dereference base/end, write the arena, or call a host service.
 * Default Arm=0 never accesses instance[3]. Arm only after initialization
 * has been confirmed in the live unsaved patch. Quiet triangles encode two
 * bytes per half-second, 400+20*byte Hz. A 200/300 Hz preamble starts each
 * 3.5-second cycle. Maximum peak 0.0002. Diagnostic only.
 */
#include "../common/compat.h"
void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *bus = (float *)ctx[1];
    uint32_t *state = (uint32_t *)instance[2];
    float fade = coef[SH_COEFF_BYPASS], arm = coef[SH_PARAM_ARM];
    int i;
    if (!mp_ready(instance, fade) || !mp_normalized(arm) || arm < 0.5f) {
        mp_silence(bus);
        return;
    }
    uint32_t count = state[0];
    float *phases = (float *)(state + 4);
    float a = phases[0], b = phases[1];
    if (!mp_normalized(a)) a = 0;
    if (!mp_normalized(b)) b = 0;
    if (count >= 154350u) count = 0;
    if (count == 0) {
        const volatile uint32_t *desc = (const volatile uint32_t *)instance[3];
        if (desc && !((uintptr_t)desc & 3u)) {
            state[1] = desc[0]; state[2] = desc[1]; state[3] = desc[2];
        } else {
            state[1] = state[2] = state[3] = 0;
        }
    }
    for (i = 0; i < SH_FRAMES; ++i) {
        unsigned int step = count / 22050u;
        float fa = 200, fb = 300;
        if (step > 0 && step <= 6) {
            unsigned int byte = (step - 1u) * 2u;
            unsigned int index = 1u + byte / 4u;
            unsigned int shift = (byte & 3u) * 8u;
            fa = 400.0f + 20.0f * (float)((state[index] >> shift) & 255u);
            fb = 400.0f + 20.0f * (float)((state[index] >> (shift + 8u)) & 255u);
        }
        float ta = a < 0.5f ? 4*a-1 : 3-4*a;
        float tb = b < 0.5f ? 4*b-1 : 3-4*b;
        bus[i] = mp_output(0, ta * 0.0002f, fade);
        bus[i + SH_CH_B_OFFSET] = mp_output(0, tb * 0.0002f, fade);
        a += fa * (1.0f / SH_SAMPLE_RATE);
        b += fb * (1.0f / SH_SAMPLE_RATE);
        if (a >= 1) a -= 1;
        if (b >= 1) b -= 1;
        ++count;
        if (count >= 154350u) count = 0;
    }
    state[0] = count; phases[0] = a; phases[1] = b;
}
