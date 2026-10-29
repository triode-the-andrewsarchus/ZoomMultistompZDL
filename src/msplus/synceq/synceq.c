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
#define ZDL_GetLabel_5(...) static mj_unused_ZDL_GetLabel_5(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)
#define ZDL_GetLabel_8(...) static mj_unused_ZDL_GetLabel_8(__VA_ARGS__)

#define SYNCEQ_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/synceq/synceq.c"
#include "synceq_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(SqState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    unsigned int k[9];
    float tempo;
    int flip, i;


    if (s->magic != SQ_MAGIC) sq_init(s);

    /* the bar tag goes out while Mozaic flips Tempo, on or off */
    tempo = mp_mj_tempo(params[SYNCEQ_TEMPO_SLOT], (float)SYNCEQ_TEMPO_UI_DEFAULT);
    flip = sq_twin_flip(s, tempo);
    if (dryBuf)
        dt_send(&s->tag, dryBuf + 8, flip,
                (unsigned int)(int)(sq_tempo_bpm(tempo) * 16.0f), dt_id(stateBase));

    if (params[0] < 0.5f) return 0;                /* switched off: input untouched */

    k[0] = mp_mj_unsigned_ui(params[SYNCEQ_LOCUT_SLOT], SYNCEQ_LOCUT_UI_DEFAULT, 50u);
    k[1] = mp_mj_unsigned_ui(params[SYNCEQ_LOW_SLOT],   SYNCEQ_LOW_UI_DEFAULT,   24u);
    k[2] = mp_mj_unsigned_ui(params[SYNCEQ_MID_SLOT],   SYNCEQ_MID_UI_DEFAULT,   24u);
    k[3] = mp_mj_unsigned_ui(params[SYNCEQ_MIDF_SLOT],  SYNCEQ_MIDF_UI_DEFAULT,  50u);
    k[4] = mp_mj_unsigned_ui(params[SYNCEQ_HIGH_SLOT],  SYNCEQ_HIGH_UI_DEFAULT,  24u);
    k[5] = mp_mj_unsigned_ui(params[SYNCEQ_HICUT_SLOT], SYNCEQ_HICUT_UI_DEFAULT, 50u);
    k[6] = mp_mj_unsigned_ui(params[SYNCEQ_DRIVE_SLOT], SYNCEQ_DRIVE_UI_DEFAULT, 100u);
    k[7] = 0u;
    k[8] = mp_mj_unsigned_ui(params[SYNCEQ_LEVEL_SLOT], SYNCEQ_LEVEL_UI_DEFAULT, 24u);

    sq_prepare(s, k);
    sq_process(s, fxBuf, 8);                     /* mono: left half in place */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 50.0f;
    params[6] = values[1] * 24.0f;
    params[7] = values[2] * 24.0f;
    params[8] = values[3] * 50.0f;
    params[9] = values[4] * 24.0f;
    params[10] = values[5] * 50.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 24.0f;
}

#define MJ_STATE_TYPE SqState
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
