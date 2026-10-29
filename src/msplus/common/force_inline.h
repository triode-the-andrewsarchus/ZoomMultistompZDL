/* Large kernels make TI's code-growth heuristic outline plain static inline
 * guards. The leaf-only verifier correctly rejects that. Force these shared
 * safety checks inline; never remove them or allow calls to work around it.
 */
#ifndef MSPLUS_FORCE_INLINE_H
#define MSPLUS_FORCE_INLINE_H
#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_ready)
#pragma FUNC_ALWAYS_INLINE(mp_normalized)
#pragma FUNC_ALWAYS_INLINE(mp_silence)
#pragma FUNC_ALWAYS_INLINE(mp_input)
#pragma FUNC_ALWAYS_INLINE(mp_output)
#pragma FUNC_ALWAYS_INLINE(mp_arena_state)
#endif
#include "compat.h"
#endif
