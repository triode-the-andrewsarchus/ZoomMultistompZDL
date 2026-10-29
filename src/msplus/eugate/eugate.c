/* Matujuice v1.5 DSP by Luca Matturro, MIT; see ../MATUJUICE-LICENSE.
 * Pristine DSP core is included from the pinned dependency. Only the legacy
 * entry glue is adapted here. Two eight-sample calls preserve its timing.
 * The legacy dry-buffer tag transport has no Plus mapping: pass NULL to its
 * supported no-tag path. No firmware buffers beyond ctx[1] are accessed.
 */
#include "../common/force_inline.h"
#include "../common/matujuice_controls.h"
/* Unreferenced legacy UI renderers are internal so TI can discard them. */
#define ZDL_GetLabel_1(...) static mj_unused_ZDL_GetLabel_1(__VA_ARGS__)
#define ZDL_GetLabel_4(...) static mj_unused_ZDL_GetLabel_4(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define EUGATE_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/eugate/eugate.c"
#include "eugate_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(ChState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    ChParams P;
    float u[9];
    int i;



    u[0] = mp_mj_ui(params[EUGATE_NOTES_SLOT],  (float)EUGATE_NOTES_UI_DEFAULT,  63.0f);
    u[1] = mp_mj_ui(params[EUGATE_STEPS_SLOT], (float)EUGATE_STEPS_UI_DEFAULT, 63.0f);
    u[2] = mp_mj_ui(params[EUGATE_SHIFT_SLOT], (float)EUGATE_SHIFT_UI_DEFAULT, 63.0f);
    u[3] = mp_mj_ui(params[EUGATE_SWING_SLOT], (float)EUGATE_SWING_UI_DEFAULT, 100.0f);
    u[4] = mp_mj_ui(params[EUGATE_RESET_SLOT],  (float)EUGATE_RESET_UI_DEFAULT,  3.0f);
    u[5] = mp_mj_ui(params[EUGATE_GAP_SLOT], (float)EUGATE_GAP_UI_DEFAULT, 50.0f);
    u[6] = mp_mj_ui(params[EUGATE_SOFT_SLOT],  (float)EUGATE_SOFT_UI_DEFAULT,  100.0f);
    u[7] = mp_mj_tempo(params[EUGATE_TEMPO_SLOT], (float)EUGATE_TEMPO_UI_DEFAULT);
    u[8] = mp_mj_ui(params[EUGATE_MIX_SLOT],   (float)EUGATE_MIX_UI_DEFAULT,   100.0f);

    if (s->magic != CH_MAGIC) ch_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    u[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0, u[7], dt_id(stateBase));
    ch_prepare(&P, u);
    if (params[0] < 0.5f) {                      /* effect switched off: input untouched */
        s->was_off = 1u;
        if (ch_twin_flip(s, u[7])) { s->pp = 0.0f; s->pos = 0u; }   /* still follows the bar */
        ch_idle(s, &P, 8);                       /* and the pattern clock keeps running */
        return 0;
    }
    if (s->was_off) {                            /* the pedal was just turned on */
        if (P.sync == 2u) { s->pp = 0.0f; s->pos = 0u; }
        s->was_off = 0u;
    }
    if (ch_twin_flip(s, u[7])) { s->pp = 0.0f; s->pos = 0u; }   /* sync reset: step 1 now */
    ch_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 63.0f;
    params[6] = values[1] * 63.0f;
    params[7] = values[2] * 63.0f;
    params[8] = values[3] * 100.0f;
    params[9] = values[4] * 3.0f;
    params[10] = values[5] * 50.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE ChState
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
