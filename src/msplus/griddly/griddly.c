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
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)
#define ZDL_GetLabel_8(...) static mj_unused_ZDL_GetLabel_8(__VA_ARGS__)

#define GRIDDLY_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/griddly/griddly.c"
#include "griddly_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(GdState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    GdParams P;
    float u[9];
    int i, tw;



    u[0] = mp_mj_ui(params[GRIDDLY_TYPE_SLOT],  (float)GRIDDLY_TYPE_UI_DEFAULT,  5.0f);
    u[1] = mp_mj_ui(params[GRIDDLY_TIME_SLOT],  (float)GRIDDLY_TIME_UI_DEFAULT,  113.0f);
    u[2] = mp_mj_ui(params[GRIDDLY_FDBK_SLOT],  (float)GRIDDLY_FDBK_UI_DEFAULT,  120.0f);
    u[3] = mp_mj_ui(params[GRIDDLY_TONE_SLOT],  (float)GRIDDLY_TONE_UI_DEFAULT,  100.0f);
    u[4] = mp_mj_ui(params[GRIDDLY_CHAR_SLOT],  (float)GRIDDLY_CHAR_UI_DEFAULT,  100.0f);
    u[5] = mp_mj_ui(params[GRIDDLY_DUCK_SLOT],  (float)GRIDDLY_DUCK_UI_DEFAULT,  100.0f);
    u[6] = mp_mj_ui(params[GRIDDLY_MIX_SLOT],   (float)GRIDDLY_MIX_UI_DEFAULT,   100.0f);
    u[7] = mp_mj_tempo(params[GRIDDLY_TEMPO_SLOT], (float)GRIDDLY_TEMPO_UI_DEFAULT);
    u[8] = mp_mj_ui(params[GRIDDLY_TAIL_SLOT],  (float)GRIDDLY_TAIL_UI_DEFAULT,  1.0f);

    if (s->magic != GD_MAGIC) gd_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    u[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0, u[7], dt_id(stateBase));
    if (gd_clearing(s)) return 0;                  /* first ~31 ms after loading: dry */

    gd_prepare(&P, u, params[0] >= 0.5f);
    tw = (u[7] > 240.0f) ? 1 : 0;                /* sync reset, followed while off too */
    if (s->twin >= 0 && tw != s->twin) gd_restart(s, &P);
    s->twin = tw;
    gd_process(s, &P, fxBuf, 8);                 /* mono: left half in place */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 5.0f;
    params[6] = values[1] * 113.0f;
    params[7] = values[2] * 120.0f;
    params[8] = values[3] * 100.0f;
    params[9] = values[4] * 100.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 1.0f;
}

#define MJ_STATE_TYPE GdState
#define MJ_OWN_BYPASS 1
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
