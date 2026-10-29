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

#define DIRTBOX_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/dirtbox/dirtbox.c"
#include "dirtbox_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(AbState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    AbParams P;
    float k[9];
    int i;


    if (params[0] < 0.5f) return 0;


    /* the nine knobs sit in consecutive slots (checked below at compile time);
     * one loop keeps one copy of ab_knob. k[] starts at each knob's default. */
    k[0] = (float)DIRTBOX_MODEL_UI_DEFAULT; k[1] = (float)DIRTBOX_DRIVE_UI_DEFAULT;
    k[2] = (float)DIRTBOX_TONE_UI_DEFAULT;  k[3] = (float)DIRTBOX_LOW_UI_DEFAULT;
    k[4] = (float)DIRTBOX_MID_UI_DEFAULT;   k[5] = (float)DIRTBOX_HIGH_UI_DEFAULT;
    k[6] = (float)DIRTBOX_ZNR_UI_DEFAULT;   k[7] = (float)DIRTBOX_LEVEL_UI_DEFAULT;
    k[8] = (float)DIRTBOX_MIX_UI_DEFAULT;
    AB_NO_UNROLL
    for (i = 0; i < 9; i++) {
        float im = 0.01f;                                    /* 0..100 knobs   */
        if (i == 0) im = 0.16666667f;                        /* Model 0..6     */
        if (i >= 3 && i <= 5) im = 0.041666668f;             /* EQ 0..24       */
        k[i] = mp_mj_knob(params[DIRTBOX_MODEL_SLOT + i], k[i], im);
    }

    ab_prepare(&P, k);
    if (s->magic != AB_MAGIC) ab_init(s, &P);
    ab_process(s, &P, fxBuf, 8);                 /* mono: left half in place   */


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 6.0f;
    params[6] = values[1] * 100.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 24.0f;
    params[9] = values[4] * 24.0f;
    params[10] = values[5] * 24.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 100.0f;
    params[13] = values[8] * 100.0f;
}

#define MJ_STATE_TYPE AbState
#define MJ_PARAM_COUNT 9
#define MJ_PACKED_HEADER_BYTES sizeof(AbState)
#include "../common/matujuice_kernel.h"
