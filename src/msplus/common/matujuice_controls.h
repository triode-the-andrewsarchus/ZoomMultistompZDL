/* Plus supplies normalized coefficients with a known UI maximum. Convert
 * explicitly to screen integers; do not guess whether legacy handler floats
 * are fractions or UI integers (notably Scrub Pos spans 0..600).
 * Signatures retain the unused fallback argument used by the old entry glue.
 */
#ifndef MSPLUS_MATUJUICE_CONTROLS_H
#define MSPLUS_MATUJUICE_CONTROLS_H
#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_mj_ui)
#pragma FUNC_ALWAYS_INLINE(mp_mj_knob)
#pragma FUNC_ALWAYS_INLINE(mp_mj_tempo)
#pragma FUNC_ALWAYS_INLINE(mp_mj_unsigned_ui)
#endif
static inline float mp_mj_ui(float value, float fallback, float maximum)
{
    float ui = (float)(int)(value + 0.5f);
    if (ui < 0) ui = 0;
    if (ui > maximum) ui = maximum;
    return ui;
}
static inline float mp_mj_knob(float value, float fallback, float inverse_maximum)
{
    float normalized = (float)(int)(value + 0.5f) * inverse_maximum;
    return normalized > 1 ? 1 : normalized;
}
static inline float mp_mj_tempo(float value, float fallback)
{
    return (float)(int)(value + 0.5f);
}
/* TI float-to-unsigned needs a runtime helper; signed conversion first is
 * exact here because all screen values are bounded to at most 600. */
static inline unsigned int mp_mj_unsigned_ui(float value, float fallback, float maximum)
{
    return (unsigned int)(int)mp_mj_ui(value, fallback, maximum);
}
#endif
