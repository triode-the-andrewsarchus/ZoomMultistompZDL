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

#define WAVEFOLD_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/wavefold/wavefold.c"
#include "wavefold_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(WfState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    WfParams P;
    float k[5];
    int i;


    if (params[0] < 0.5f) return 0;


    k[0] = mp_mj_knob(params[WAVEFOLD_DRIVE_SLOT], (float)WAVEFOLD_DRIVE_UI_DEFAULT, 0.01f);
    k[1] = mp_mj_knob(params[WAVEFOLD_SYMM_SLOT],  (float)WAVEFOLD_SYMM_UI_DEFAULT,  0.01f);
    k[2] = mp_mj_knob(params[WAVEFOLD_TONE_SLOT],  (float)WAVEFOLD_TONE_UI_DEFAULT,  0.01f);
    k[3] = mp_mj_knob(params[WAVEFOLD_LEVEL_SLOT], (float)WAVEFOLD_LEVEL_UI_DEFAULT, 0.01f);
    k[4] = mp_mj_knob(params[WAVEFOLD_MIX_SLOT],   (float)WAVEFOLD_MIX_UI_DEFAULT,   0.01f);

    wf_prepare(&P, k);
    if (s->magic != WF_MAGIC) wf_init(s, &P);
    wf_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 100.0f;
    params[6] = values[1] * 100.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 100.0f;
    params[9] = values[4] * 100.0f;
}

#define MJ_STATE_TYPE WfState
#define MJ_PARAM_COUNT 5
#include "../common/matujuice_kernel.h"
