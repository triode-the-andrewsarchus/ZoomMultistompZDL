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
validation; full integration and hardware qualification remain
to be completed. `tools/msplus/resample_coeffs.py` reproduces the tables.

The offline TI integration probe passes the unchanged Stomphacks validator.
Target tables use its existing `const_blob` manifest support (symbol
`plateau_src_blob`, 4,224 words, init `resample_coeffs.bin`) so the parameter
table remains first in `.const`. The native header has identical generated
coefficients; binary equality is tested. No SRC probe was installed.

The mechanically derived float32 reverb core is now checked against the pinned
upstream double implementation. Six profiles cover impulse tails, minimum and
maximum size, 500 ms predelay, modulation depth/shape and independent filters.
A third test variant verifies that explicit bounded initialization matches the
ordinary adapted constructors. Run `python -m unittest discover -s tools/msplus
-p test_plateau.py -v` in the project venv. The oracle's sole upstream-source
change enlarges its undersized predelay storage row; DSP equations are retained.

The core/SRC-only checkpoint passed the unchanged Stomphacks validator at
16,704 bytes of text, including leaf/runtime-helper, relocation, parameter-table
and code-size checks. The current fixture also includes the complete output
processing and remains offline; see the current size limitation below. Explicit initialization retains the
original float operation order and zero-initializes scalar members correctly;
the native tests also run six extreme profiles under AddressSanitizer and
UndefinedBehaviorSanitizer. Full controls, cooperative output-stage initialization and hardware
qualification remain outstanding. No Plateau integration probe has been installed.

To reproduce the offline build (after `plateau_derive.py`), run:

```sh
ZOOM_TI_CGT="$PWD/build/msplus/ti/ti-cgt-c6000_8.3.15" \
  build/msplus/venv/bin/python build/msplus/stomphacks/tools/zd2_make_effect.py \
  src/msplus/plateau/offline-core-probe/manifest.json
```

`offline-core-probe` is deliberately outside the installable port inventory.
Its private development identity is not Plateau's final identity. Its artifact
is a compile/integration fixture, not a complete or hardware-qualified effect;
do not install it. The build report is under that fixture's ignored `build/`.


Architecture review against `pre-velvet-plateau` reports generated compatibility
header duplication. These headers are mechanical C++ inline-syntax adaptations
of the shared C implementation, generated from that implementation rather than
independently maintained copies. The TI C++ frontend rejects its C-only inline
pragmas. Keeping the adaptation local also preserves the exact shared source
fingerprints of all 35 already qualified effects. The broader report includes
historical HIL JSON snapshots and the already qualified Velvet implementation;
this core adds no dependency cycles or maximum-complexity increase.

Output-stage implementation in `output.h` retains all eleven gain modes and
its 10 ms lookahead / 600 ms release limiter. Forty-three mode/drive profiles
match the pinned original processing within 0.0003 absolute / 0.2% relative
sample error. The full-drive fold case is tested separately: upstream uses
`fmod(x,0)` there, while this port returns a finite zero fold signal. The original
LMTR wrapper's right/left output-reference ordering is preserved. Detector
accumulation uses compensated float summation; the amplifier preserves the
original 8192-step quantization by evaluating its quantized table entries.

The soft limiter uses the same 320-sample minimum window with bounded fixed
storage, the original three box lengths (130/108/84), and prefix-sum/reset
ordering. A fixed minimum tree replaces Signalsmith's dynamically allocated
peak-hold storage. Non-audio histories and pre-limiter delay samples are stored
at very low scales and restored on read, so reused delay memory does not contain
unscaled control sums or amplified pre-limiter signals. Only the small control
header is encoded; large histories remain outside it.

Run the output comparisons with `python -m unittest discover -s tools/msplus
-p test_plateau_output.py -v`. The test oracle extracts the original processing
and removes its LED updates; it also explicitly resets the original detector
buffer to reproduce firmware static initialization between test renders.

Current integration: **17,920 bytes of text versus a 17,536-byte three-control
probe limit** (384 bytes over). The final ten-control cap is 18,432 bytes, but its
remaining controls are not yet implemented. The build is still rejected by the
unchanged validator. Sharing the original stereo/modulation arithmetic and
output stage flags reduced the first full integration from 24,160 bytes without
removing modes. Do not install this fixture: startup is not yet cooperatively
bounded and it lacks the final control/safety integration and hardware checks.

Architecture review: the output mode flag table consolidates the original
repeated branches and shared DSP stages. The remaining mode dispatcher has
CCN 20 for eleven distinct pipelines. A separate always-inline coloration
helper reduced source-level CCN but increased TI text from 17,920 to 18,368
bytes; it was reverted because the bounded target budget takes precedence over
that metric. The new license duplication is the required retained MIT notice.
Generated C++ compatibility copies and historical HIL snapshots remain the
previously documented duplication; no new dependency cycle was introduced.
