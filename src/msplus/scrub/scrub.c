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
#define ZDL_GetLabel_2(...) static mj_unused_ZDL_GetLabel_2(__VA_ARGS__)
#define ZDL_GetLabel_0(...) static mj_unused_ZDL_GetLabel_0(__VA_ARGS__)
#define ZDL_GetLabel_4(...) static mj_unused_ZDL_GetLabel_4(__VA_ARGS__)
#define ZDL_GetLabel_5(...) static mj_unused_ZDL_GetLabel_5(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define SCRUB_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/scrub/scrub.c"
#include "scrub_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(ScState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    ScParams P;
    float u[8];
    int i, flip;



    u[0] = sc_ui_pos(params[SCRUB_POS_SLOT], (float)SCRUB_POS_UI_DEFAULT);
    u[1] = mp_mj_ui(params[SCRUB_GRAIN_SLOT],  (float)SCRUB_GRAIN_UI_DEFAULT,  112.0f);
    u[2] = mp_mj_ui(params[SCRUB_REC_SLOT],    (float)SCRUB_REC_UI_DEFAULT,    2.0f);
    u[3] = mp_mj_ui(params[SCRUB_GLIDE_SLOT], (float)SCRUB_GLIDE_UI_DEFAULT, 100.0f);
    u[4] = mp_mj_ui(params[SCRUB_DIR_SLOT],    (float)SCRUB_DIR_UI_DEFAULT,    3.0f);
    u[5] = mp_mj_ui(params[SCRUB_SPRAY_SLOT],  (float)SCRUB_SPRAY_UI_DEFAULT,  100.0f);
    u[6] = mp_mj_ui(params[SCRUB_MIX_SLOT],    (float)SCRUB_MIX_UI_DEFAULT,    100.0f);
    u[7] = mp_mj_tempo(params[SCRUB_TEMPO_SLOT], (float)SCRUB_TEMPO_UI_DEFAULT);

    if (s->magic != SC_MAGIC) sc_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    u[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0, u[7], dt_id(stateBase));
    if (sc_clearing(s)) return 0;                  /* first ~12 ms after loading: dry */

    sc_prepare(&P, u);
    flip = sc_twin_flip(s, u[7]);                /* followed while off too */
    if (params[0] < 0.5f) {                      /* effect switched off */
        s->was_off = 1;
        sc_bypassed(s, P.mode, fxBuf, 8);
        return 0;
    }
    if (s->was_off) { sc_switched_on(s, &P); s->was_off = 0; }
    else if (flip && s->started) sc_restart(s, &P);   /* sync reset: new grain now */
    sc_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 600.0f;
    params[6] = values[1] * 112.0f;
    params[7] = values[2] * 2.0f;
    params[8] = values[3] * 100.0f;
    params[9] = values[4] * 3.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
}

#define MJ_STATE_TYPE ScState
#define MJ_PARAM_COUNT 8
#include "../common/matujuice_kernel.h"
