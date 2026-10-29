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
#define ZDL_GetLabel_3(...) static mj_unused_ZDL_GetLabel_3(__VA_ARGS__)
#define ZDL_GetLabel_4(...) static mj_unused_ZDL_GetLabel_4(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define BREATHER_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/breather/breather.c"
#include "breather_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(PuState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    PuParams P;
    float u[9];
    int i, flip;



    u[0] = mp_mj_ui(params[BREATHER_TARGT_SLOT], (float)BREATHER_TARGT_UI_DEFAULT, 3.0f);
    u[1] = mp_mj_ui(params[BREATHER_SHAPE_SLOT], (float)BREATHER_SHAPE_UI_DEFAULT, 2.0f);
    u[2] = mp_mj_ui(params[BREATHER_DEPTH_SLOT], (float)BREATHER_DEPTH_UI_DEFAULT, 100.0f);
    u[3] = mp_mj_ui(params[BREATHER_DIV_SLOT],   (float)BREATHER_DIV_UI_DEFAULT,   4.0f);
    u[4] = mp_mj_ui(params[BREATHER_SHIFT_SLOT], (float)BREATHER_SHIFT_UI_DEFAULT, 100.0f);
    u[5] = mp_mj_ui(params[BREATHER_CURVE_SLOT], (float)BREATHER_CURVE_UI_DEFAULT, 100.0f);
    u[6] = mp_mj_ui(params[BREATHER_VERB_SLOT],  (float)BREATHER_VERB_UI_DEFAULT,  100.0f);
    u[7] = mp_mj_tempo(params[BREATHER_TEMPO_SLOT], (float)BREATHER_TEMPO_UI_DEFAULT);
    u[8] = mp_mj_ui(params[BREATHER_SIZE_SLOT],  (float)BREATHER_SIZE_UI_DEFAULT,  100.0f);

    if (s->magic != PU_MAGIC) pu_init(s);
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    u[7] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0, u[7], dt_id(stateBase));
    pu_prepare(&P, u);
    flip = pu_twin_flip(s, u[7]);
    if (flip) { s->bp = 0.0f; s->since_flip = 0u; }  /* sync reset: beat 1 now */
    else if (s->since_flip < PU_HOST_BLOCKS) s->since_flip++;

    if (params[0] < 0.5f) {                      /* effect switched off: input untouched */
        if (!s->was_off) s->clear_pos = 0;       /* the reverb starts clean when back on */
        s->was_off = 1u;
        pu_clear_step(s);
        s->bp += P.inc * 8.0f;                   /* the clock keeps running */
        if (s->bp >= PU_BAR) s->bp -= PU_BAR;
        return 0;
    }
    if (s->was_off) {                            /* the pedal was just turned on */
        if (s->since_flip >= PU_HOST_BLOCKS) s->bp = 0.0f;   /* no host: stomp on the one */
        s->was_off = 0u;
    }
    pu_clear_step(s);
    pu_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 3.0f;
    params[6] = values[1] * 2.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 4.0f;
    params[9] = values[4] * 100.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE PuState
#define MJ_PARAM_COUNT 9
#define MJ_PACKED_HEADER_BYTES offsetof(PuState, rev)
#include "../common/matujuice_kernel.h"
