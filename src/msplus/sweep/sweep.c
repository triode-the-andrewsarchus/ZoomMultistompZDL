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
#define ZDL_GetLabel_5(...) static mj_unused_ZDL_GetLabel_5(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define SWEEP_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/sweep/sweep.c"
#include "sweep_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(SwState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    SwParams P;
    float u[9], bpm;
    int i, flip;



    u[0] = mp_mj_ui(params[SWEEP_TYPE_SLOT],  (float)SWEEP_TYPE_UI_DEFAULT,  7.0f);
    u[1] = mp_mj_ui(params[SWEEP_RATE_SLOT],  (float)SWEEP_RATE_UI_DEFAULT,  115.0f);
    u[2] = mp_mj_ui(params[SWEEP_DEPTH_SLOT], (float)SWEEP_DEPTH_UI_DEFAULT, 100.0f);
    u[3] = mp_mj_ui(params[SWEEP_CNTR_SLOT],  (float)SWEEP_CNTR_UI_DEFAULT,  100.0f);
    u[4] = mp_mj_ui(params[SWEEP_RESO_SLOT],  (float)SWEEP_RESO_UI_DEFAULT,  100.0f);
    u[5] = mp_mj_ui(params[SWEEP_SHAPE_SLOT], (float)SWEEP_SHAPE_UI_DEFAULT, 5.0f);
    u[6] = mp_mj_ui(params[SWEEP_TONE_SLOT],  (float)SWEEP_TONE_UI_DEFAULT,  100.0f);
    u[7] = mp_mj_tempo(params[SWEEP_TEMPO_SLOT], (float)SWEEP_TEMPO_UI_DEFAULT);
    u[8] = mp_mj_ui(params[SWEEP_MIX_SLOT],   (float)SWEEP_MIX_UI_DEFAULT,   100.0f);

    if (s->magic != SW_MAGIC) sw_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    u[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0, u[7], dt_id(stateBase));
    bpm = sw_tempo_bpm(u[7]);
    flip = sw_twin_flip(s, u[7]);
    sw_prepare(s, &P, u, bpm);
    if (params[0] < 0.5f) {                      /* effect switched off: input untouched */
        s->was_off = 1u;
        sw_advance(s, &P, flip);                 /* the sweep keeps running, follows the bar */
        return 0;
    }
    if (s->was_off) sw_wake(s);
    if (P.type < 2u)      sw_phaser(s, &P, fxBuf, 8);
    else if (P.type < 4u) sw_flanger(s, &P, fxBuf, 8);
    else                  sw_filter(s, &P, fxBuf, 8);
    sw_advance(s, &P, flip);


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 7.0f;
    params[6] = values[1] * 115.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 100.0f;
    params[9] = values[4] * 100.0f;
    params[10] = values[5] * 5.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE SwState
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
