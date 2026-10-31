# Plateau / Campestria — MS-70CDR+ port in development

Upstream: digitalartifactmusic/PlateauNEVersio,
`4218b072e7420dd788cd3c98c36b3eba445f8886`, based on Dale Johnson's
Valley Plateau / Dattorro reverb. GPL-3.0-or-later; retain the accompanying
licenses and third-party notices. This directory is not yet an installable
or hardware-qualified effect.

Implementation requirements:

- Retain the 32 kHz reverb topology, modulation range, maximum size 4,
  diffusion, freeze, filters, gain stages and eleven output modes.
- Replace rectangular/global SDRAM allocation with bounded per-instance arena
  buffers; cap predelay at 500 ms as authorized. Initialize cooperatively.
- Supply anti-aliasing conversion to/from the 44.1 kHz host; float32 DSP.
- Retain all DSP safety and transfer checks; never save an experimental patch.
- Fit ten coefficient controls: Mix, Size, Decay, Pre, Speed, Depth, Hold,
  Mode, Edit and Value. Hold selects run/freeze/clear; Mode selects the original
  eleven output modes. Edit/Value retain the source's multifunction Tone
  control for input/tank filters, diffusion, input gain, output drive,
  modulation shape and depth lock. Changing Edit selects a target; only a
  subsequent Value movement changes it, preserving other settings. As with
  the source's switches/knob, the scalar Value display is not a readout of
  every stored advanced setting. Chain reinitialization restores defaults.
- Validate the core against the pinned upstream DSP, output stages separately,
  then actual hardware response/tails, changing delay times, zero-input
  stability, clear/freeze and stock-effect restoration.

The advanced-control mapping is needed because the complete upstream firmware
has more independent settings than the Plus toolchain's ten safe knob slots.
It preserves the source's switch-selected editing approach rather than silently
omitting output modes or independent filter settings.

The 64-tap, 32-phase input/output SRC is implemented in `resample.h`,
with readonly generated coefficient tables. Four native tests pass: exact
32,000 internal frames per 44,100 host frames, unity DC, under 0.03 dB
round-trip gain error through 12 kHz, exact channel isolation, and more than
65 dB rejection for the tested 16–21 kHz input tones. This is component-level
validation; the reverb core, output stages and hardware qualification remain
to be completed. `tools/msplus/resample_coeffs.py` reproduces the tables.
