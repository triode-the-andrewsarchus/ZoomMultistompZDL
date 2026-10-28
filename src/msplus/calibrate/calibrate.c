/* Quiet diagnostic, not a musical release: known-amplitude triangles measure
 * DSP-bus -> interface return scaling without depending on input calibration.
 * Bus A is 997 Hz, bus B 1499 Hz. Peak <=0.001; init/coef guards still apply.
 */
#include "../common/compat.h"
void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *bus = (float *)ctx[1];
    float *state = (float *)instance[2];
    float fade = coef[SH_COEFF_BYPASS], level = coef[SH_PARAM_LEVEL];
    int i;
    if (!mp_ready(instance, fade) || !mp_normalized(level)) {
        mp_silence(bus);
        return;
    }
    float a = state[0], b = state[1];
    if (!mp_normalized(a)) a = 0;
    if (!mp_normalized(b)) b = 0;
    float amplitude = 0.001f * level;
    for (i = 0; i < SH_FRAMES; ++i) {
        float ta = a < 0.5f ? 4.0f * a - 1.0f : 3.0f - 4.0f * a;
        float tb = b < 0.5f ? 4.0f * b - 1.0f : 3.0f - 4.0f * b;
        bus[i] = mp_output(bus[i], ta * amplitude, fade);
        bus[i + SH_CH_B_OFFSET] = mp_output(bus[i + SH_CH_B_OFFSET], tb * amplitude, fade);
        a += 997.0f / SH_SAMPLE_RATE;
        b += 1499.0f / SH_SAMPLE_RATE;
        if (a >= 1) a -= 1;
        if (b >= 1) b -= 1;
    }
    state[0] = a; state[1] = b;
}
