/* Matujuice v1.5 DSP by Luca Matturro, MIT; see ../MATUJUICE-LICENSE.
 * Pristine DSP core is included from the pinned dependency. Only the legacy
 * entry glue is adapted here. Two eight-sample calls preserve its timing.
 * The legacy dry-buffer tag transport has no Plus mapping: pass NULL to its
 * supported no-tag path. No firmware buffers beyond ctx[1] are accessed.
 */
#include "../common/force_inline.h"
#include "../common/matujuice_controls.h"
/* Unreferenced legacy UI renderers are internal so TI can discard them. */
#define ZDL_GetLabel_0(...) static mj_unused_ZDL_GetLabel_0(__VA_ARGS__)
#define ZDL_GetLabel_1(...) static mj_unused_ZDL_GetLabel_1(__VA_ARGS__)
#define ZDL_GetLabel_2(...) static mj_unused_ZDL_GetLabel_2(__VA_ARGS__)
#define ZDL_GetLabel_3(...) static mj_unused_ZDL_GetLabel_3(__VA_ARGS__)
#define ZDL_GetLabel_4(...) static mj_unused_ZDL_GetLabel_4(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define FORMANT_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/formant/formant.c"
#include "formant_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(ChState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    ChParams P;
    float k[9];
    int i;



    SR_NOUNROLL
    for (i = 0; i < 9; i++) {                    /* knobs in a row, Tempo (7) apart */
        if (i == 7) continue;
        k[i] = mp_mj_knob(params[FORMANT_CHOIR_SLOT + i],
                       (float)((i == 0) ? FORMANT_CHOIR_UI_DEFAULT : (i == 1) ? FORMANT_SIZE_UI_DEFAULT
                             : (i == 2) ? FORMANT_CHORD_UI_DEFAULT : (i == 3) ? FORMANT_SING_UI_DEFAULT
                             : (i == 4) ? FORMANT_PACE_UI_DEFAULT : (i == 5) ? FORMANT_FEEL_UI_DEFAULT
                             : (i == 6) ? FORMANT_GLIDE_UI_DEFAULT : FORMANT_MIX_UI_DEFAULT),
                       (i == 0 || i == 4) ? 0.0625f : (i == 1) ? 0.2f : (i == 2) ? 0.041666668f
                       : (i == 3) ? 0.09090909f : 0.01f);   /* 1 / each knob's max */
    }

    if (s->magic != CH_MAGIC) ch_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    k[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0,
                    mp_mj_tempo(params[FORMANT_TEMPO_SLOT], (float)FORMANT_TEMPO_UI_DEFAULT),
                    dt_id(stateBase)) * 0.0022675737f;   /* 1/441 */
    ch_prepare(s, &P, k);                        /* a Tempo flip is a downbeat */
    ch_tick(s, &P);
    if (params[0] < 0.5f) {                      /* switched off: input untouched, the */
        s->was_off = 1;                          /* movement keeps time with the bar   */
        return 0;
    }
    if (s->was_off) { ch_clear(s); s->was_off = 0; }
    ch_process(s, &P, fxBuf);                    /* mono: left half in place */

    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 16.0f;
    params[6] = values[1] * 5.0f;
    params[7] = values[2] * 24.0f;
    params[8] = values[3] * 11.0f;
    params[9] = values[4] * 16.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE ChState
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
