/* Matujuice v1.5 DSP by Luca Matturro, MIT; see ../MATUJUICE-LICENSE.
 * Pristine DSP core is included from the pinned dependency. Only the legacy
 * entry glue is adapted here. Two eight-sample calls preserve its timing.
 * The legacy dry-buffer tag transport has no Plus mapping: pass NULL to its
 * supported no-tag path. No firmware buffers beyond ctx[1] are accessed.
 */
#include "../common/force_inline.h"
#include "../common/matujuice_controls.h"
/* Unreferenced legacy UI renderers are internal so TI can discard them. */
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)
#define ZDL_GetLabel_5(...) static mj_unused_ZDL_GetLabel_5(__VA_ARGS__)
#define ZDL_GetLabel_4(...) static mj_unused_ZDL_GetLabel_4(__VA_ARGS__)
#define ZDL_GetLabel_6(...) static mj_unused_ZDL_GetLabel_6(__VA_ARGS__)

#define DUALSHIFT_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/dualshft/dualshft.c"
#include "dualshft_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(DualShift *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    DualShiftParams P;
    float k[9];
    int i;



    k[0] = mp_mj_knob(params[DUALSHFT_PTCH1_SLOT], (float)DUALSHFT_PTCH1_UI_DEFAULT, 0.0151515152f);
    k[1] = mp_mj_knob(params[DUALSHFT_PTCH2_SLOT], (float)DUALSHFT_PTCH2_UI_DEFAULT, 0.0151515152f);
    k[2] = mp_mj_knob(params[DUALSHFT_DLY1_SLOT],   (float)DUALSHFT_DLY1_UI_DEFAULT,   0.008928571f);
    k[3] = mp_mj_knob(params[DUALSHFT_DLY2_SLOT],   (float)DUALSHFT_DLY2_UI_DEFAULT,   0.008928571f);
    ds_ensure_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    k[4] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0,
                    mp_mj_tempo(params[DUALSHFT_TEMPO_SLOT], (float)DUALSHFT_TEMPO_UI_DEFAULT),
                    dt_id(stateBase)) * 0.0022675737f;   /* 1/441 */
    k[5] = mp_mj_knob(params[DUALSHFT_DIV_SLOT],    (float)DUALSHFT_DIV_UI_DEFAULT,    0.0625f);
    k[6] = mp_mj_knob(params[DUALSHFT_DEPTH_SLOT],  (float)DUALSHFT_DEPTH_UI_DEFAULT,  0.0125f);
    k[7] = mp_mj_knob(params[DUALSHFT_SHAPE_SLOT],  (float)DUALSHFT_SHAPE_UI_DEFAULT,  0.1666667f);
    k[8] = mp_mj_knob(params[DUALSHFT_MIX_SLOT],    (float)DUALSHFT_MIX_UI_DEFAULT,    0.01f);

    ds_prepare(s, &P, k);
    if (params[0] < 0.5f) {                      /* effect switched off: input untouched, */
        if (P.retrig) s->lfo_phase = 0.0f;       /* but the LFO keeps time with the bar   */
        s->lfo_phase += P.lfo_inc * 8.0f;
        if (s->lfo_phase >= 1.0f) s->lfo_phase -= 1.0f;
        return 0;
    }
    ds_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 66.0f;
    params[6] = values[1] * 66.0f;
    params[7] = values[2] * 112.0f;
    params[8] = values[3] * 112.0f;
    params[9] = values[4] * 16.0f;
    params[10] = values[5] * 80.0f;
    params[11] = values[6] * 6.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE DualShift
#define MJ_PARAM_COUNT 9
#define MJ_PACKED_HEADER_BYTES offsetof(DualShift, ring)
#include "../common/matujuice_kernel.h"
