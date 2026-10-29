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
#define ZDL_GetLabel_6(...) static mj_unused_ZDL_GetLabel_6(__VA_ARGS__)
#define ZDL_GetLabel_8(...) static mj_unused_ZDL_GetLabel_8(__VA_ARGS__)
#define ZDL_GetLabel_7(...) static mj_unused_ZDL_GetLabel_7(__VA_ARGS__)

#define DUBSIREN_HOST_TEST 1
#include "../../../build/msplus/matujuice/src/custom/dubsiren/dubsiren.c"
#include "dubsiren_params.h"

#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_half)
#pragma FUNC_ALWAYS_INLINE(mp_raw_controls)
#endif
static inline int mp_half(SirenState *s, const float *params, float *fxBuf)
{
    float *dryBuf = 0;
    uintptr_t stateBase = (uintptr_t)s;
    SirenParams P;
    float k[9];
    int i, foot;


    foot = params[0] >= 0.5f;


    k[0] = mp_mj_knob(params[DUBSIREN_TRIG_SLOT],   (float)DUBSIREN_TRIG_UI_DEFAULT,   0.3333333f);
    k[1] = mp_mj_knob(params[DUBSIREN_MODE_SLOT],   (float)DUBSIREN_MODE_UI_DEFAULT,   0.3333333f);
    k[2] = mp_mj_knob(params[DUBSIREN_PITCH_SLOT],  (float)DUBSIREN_PITCH_UI_DEFAULT,  0.01f);
    k[3] = mp_mj_knob(params[DUBSIREN_RATE_SLOT],   (float)DUBSIREN_RATE_UI_DEFAULT,   0.008928571f);
    k[4] = mp_mj_knob(params[DUBSIREN_DEPTH_SLOT],  (float)DUBSIREN_DEPTH_UI_DEFAULT,  0.01f);
    k[5] = mp_mj_knob(params[DUBSIREN_VOL_SLOT],    (float)DUBSIREN_VOL_UI_DEFAULT,    0.01f);
    k[6] = mp_mj_knob(params[DUBSIREN_TIME_SLOT],   (float)DUBSIREN_TIME_UI_DEFAULT,   0.01f);
    k[7] = mp_mj_knob(params[DUBSIREN_FDBK_SLOT],   (float)DUBSIREN_FDBK_UI_DEFAULT,   0.008f);
    if (s->magic != SR_MAGIC) sr_init(s);        /* prev_* must be valid       */
    /* bar tag: bars from earlier slots flip the Tempo copy too, FOLLOW takes their BPM */
    k[8] = dt_tempo(&s->sync, dryBuf ? dryBuf + 8 : 0,
                    mp_mj_tempo(params[DUBSIREN_TEMPO_SLOT], (float)DUBSIREN_TEMPO_UI_DEFAULT),
                    dt_id(stateBase)) * 0.0022675737f;   /* 1/441 */
    sr_prepare(s, &P, k, foot);
    sr_process(s, &P, fxBuf, 8);


    return 1;
}

static inline void mp_raw_controls(float *params, const float *values)
{
    params[5] = values[0] * 3.0f;
    params[6] = values[1] * 3.0f;
    params[7] = values[2] * 100.0f;
    params[8] = values[3] * 112.0f;
    params[9] = values[4] * 100.0f;
    params[10] = values[5] * 100.0f;
    params[11] = values[6] * 100.0f;
    params[12] = values[7] * 441.0f;
    params[13] = values[8] * 125.0f;
}

#define MJ_STATE_TYPE SirenState
#define MJ_OWN_BYPASS 1
#define MJ_PARAM_COUNT 9
#define MJ_PACKED_HEADER_BYTES offsetof(SirenState, ring)
#include "../common/matujuice_kernel.h"
