/* Keep integer/control state from being interpreted as audio after an effect
 * change. Stock CloneCho reuses delay memory without clearing it in _init.
 * Each raw 32-bit word is saved as two 16-bit integers in separate words:
 * both storage words are tiny finite float bit patterns. The raw header is
 * zero between callbacks. Audio rings outside the header are not moved.
 * No float conversion is used: every bit, including integer -1, round-trips.
 */
#ifndef MSPLUS_ARENA_STATE_H
#define MSPLUS_ARENA_STATE_H
#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_unpack_header)
#pragma FUNC_ALWAYS_INLINE(mp_pack_header)
#endif
static inline void mp_unpack_header(uintptr_t base, uintptr_t packed, unsigned int bytes)
{
    unsigned char *raw = (unsigned char *)base;
    const uint32_t *saved = (const uint32_t *)packed;
    unsigned int i;
    for (i = 0; i < bytes / 4; ++i) {
        uint32_t lo = saved[2*i], hi = saved[2*i+1];
        raw[4*i] = (unsigned char)lo;
        raw[4*i+1] = (unsigned char)(lo >> 8);
        raw[4*i+2] = (unsigned char)hi;
        raw[4*i+3] = (unsigned char)(hi >> 8);
    }
}

static inline void mp_pack_header(uintptr_t base, uintptr_t packed, unsigned int bytes)
{
    unsigned char *raw = (unsigned char *)base;
    uint32_t *saved = (uint32_t *)packed;
    unsigned int i;
    for (i = 0; i < bytes / 4; ++i) {
        saved[2*i] = (uint32_t)raw[4*i] | ((uint32_t)raw[4*i+1] << 8);
        saved[2*i+1] = (uint32_t)raw[4*i+2] | ((uint32_t)raw[4*i+3] << 8);
        raw[4*i] = raw[4*i+1] = raw[4*i+2] = raw[4*i+3] = 0;
    }
}
#endif
