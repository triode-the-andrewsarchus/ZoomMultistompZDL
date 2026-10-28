/* Port of src/airwindows/gain: normalized level multiplication. The original
 * 8x compensation for an uninitialized legacy edit handler is intentionally
 * absent: Plus provides normalized, initialized coefficients. */
#include "../common/compat.h"

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coeff = (const float *)instance[1];
    float *bus = (float *)ctx[1];
    float *state = (float *)instance[2];
    float fade = coeff[SH_COEFF_BYPASS];
    float level = coeff[SH_PARAM_LEVEL];
    int i;
    if (!mp_ready(instance, fade) || !mp_normalized(level)) {
        mp_silence(bus);
        return;
    }
    float smooth = state[0];
    if (!mp_normalized(smooth)) smooth = 0.0f;
    for (i = 0; i < SH_FRAMES; ++i) {
        smooth += 0.002f * (level - smooth);
        float a = bus[i], b = bus[i + SH_CH_B_OFFSET];
        bus[i] = mp_output(a, a * smooth, fade);
        bus[i + SH_CH_B_OFFSET] = mp_output(b, b * smooth, fade);
    }
    state[0] = smooth;
}
