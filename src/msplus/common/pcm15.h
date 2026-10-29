/* Two signed 15-bit history samples in one word whose float interpretation
 * is bounded below 1.1e-19. Preserves the full legacy ring length and costs
 * at most one 16-bit PCM count per write. Integer -1 is never stored raw.
 * These helpers are the only changes to generated Scrub/GridDly DSP cores.
 */
#ifndef MSPLUS_PCM15_H
#define MSPLUS_PCM15_H
#include <stdint.h>
#ifdef __TI_COMPILER_VERSION__
#pragma FUNC_ALWAYS_INLINE(mp_pcm_word)
#pragma FUNC_ALWAYS_INLINE(mp_pcm15_read)
#pragma FUNC_ALWAYS_INLINE(mp_pcm15_write)
#endif
static inline uint32_t mp_pcm_word(const unsigned char *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8)
        | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline int mp_pcm15_read(const short *ring, int index)
{
#ifdef MP_RAW_STATE_REFERENCE
    return ring[index];
#else
    uint32_t word = mp_pcm_word((const unsigned char *)ring + 4*(index >> 1));
    uint32_t payload = (word & 0x1fffffffu) | ((word >> 2) & 0x20000000u);
    int sample = (int)((payload >> (15*(index & 1))) & 0x7fffu);
    if (sample & 0x4000) sample -= 0x8000;
    return sample * 2;
#endif
}

static inline void mp_pcm15_write(short *ring, int index, int value)
{
#ifdef MP_RAW_STATE_REFERENCE
    ring[index] = (short)value;
#else
    unsigned char *p = (unsigned char *)ring + 4*(index >> 1);
    uint32_t word = mp_pcm_word(p);
    uint32_t payload = (word & 0x1fffffffu) | ((word >> 2) & 0x20000000u);
    unsigned int shift = 15*(index & 1);
    if (value > 32767) value = 32767;
    if (value < -32767) value = -32767;
    int sample = value < 0 ? -((-value) >> 1) : value >> 1;
    payload = (payload & ~(0x7fffu << shift)) | (((uint32_t)sample & 0x7fffu) << shift);
    word = (payload & 0x1fffffffu) | ((payload & 0x20000000u) << 2);
    p[0] = (unsigned char)word;
    p[1] = (unsigned char)(word >> 8);
    p[2] = (unsigned char)(word >> 16);
    p[3] = (unsigned char)(word >> 24);
#endif
}
#endif
