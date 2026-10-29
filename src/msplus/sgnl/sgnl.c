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
#define ZDL_GetLabel_3(...) static mj_unused_ZDL_GetLabel_3(__VA_ARGS__)
#define ZDL_GetLabel_6(...) static mj_unused_ZDL_GetLabel_6(__VA_ARGS__)

#define SGNL_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/sgnl/sgnl.c"
#include "sgnl_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(SgState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    SgParams P;
    float u[9];
    int i;



    if (params[0] < 0.5f) return 0;                /* effect bypassed */

    u[0] = mp_mj_ui(params[SGNL_LOSS_SLOT],  (float)SGNL_LOSS_UI_DEFAULT,  100.0f);
    u[1] = mp_mj_ui(params[SGNL_SIZE_SLOT],  (float)SGNL_SIZE_UI_DEFAULT,  100.0f);
    u[2] = mp_mj_ui(params[SGNL_CODEC_SLOT], (float)SGNL_CODEC_UI_DEFAULT, 100.0f);
    u[3] = mp_mj_ui(params[SGNL_FILL_SLOT],  (float)SGNL_FILL_UI_DEFAULT,  7.0f);
    u[4] = mp_mj_ui(params[SGNL_BURST_SLOT], (float)SGNL_BURST_UI_DEFAULT, 100.0f);
    u[5] = mp_mj_ui(params[SGNL_JUMP_SLOT],  (float)SGNL_JUMP_UI_DEFAULT,  100.0f);
    u[6] = mp_mj_ui(params[SGNL_LINE_SLOT],  (float)SGNL_LINE_UI_DEFAULT,  3.0f);
    u[7] = mp_mj_ui(params[SGNL_EDGE_SLOT],  (float)SGNL_EDGE_UI_DEFAULT,  100.0f);
    u[8] = mp_mj_ui(params[SGNL_MIX_SLOT],   (float)SGNL_MIX_UI_DEFAULT,   100.0f);

    sg_prepare(&P, u);
    if (s->magic != SG_MAGIC) sg_init(s);
    sg_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 100.0f;
    params[6] = values[1] * 100.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 7.0f;
    params[9] = values[4] * 100.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 3.0f;
    params[12] = values[7] * 100.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE SgState
#define MJ_PARAM_COUNT 9
#include "../common/matujuice_kernel.h"
