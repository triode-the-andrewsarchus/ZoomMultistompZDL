# Two additional MS-70CDR+ port candidates

Source inspection and offline resource accounting, 2026-10-31. The existing
34-effect category migration and final hardware audit are complete; see
[the current development result](MSPLUS-DEVELOPMENT.md#completed-category-migration-october-31).
Neither candidate has been installed or run on the pedal. This assessment is
about a stereo standalone effect, not a six-effect chain.

| Candidate | Assessment | Main constraint |
|---|---|---|
| Dynamic Velvet Decorrelator | Good candidate for a port; default operating region looks practical | Worst-case density, crossfades and kernel-renewal bursts need target profiling |
| Campestria/PlateauNEVersio | Reverb core looks feasible with adaptation; full original ranges/features are substantially harder | Delay RAM, output-limiter memory and resampling; direct source reuse is unsafe |

## Verified target envelope

The pedal is MS-70CDR+, firmware 1.10. Our measured standalone delay arena is
**705,600 bytes**, checked at runtime before access. This is a verified grant,
not a claim about the pedal's total physical RAM. Small state has **188 user
bytes** plus its init guard; substantial state must use the bounded arena.
Multi-slot ownership remains unqualified. See [memory evidence](MSPLUS-MEMORY-RESEARCH.md).

The [Stomphacks ABI](https://github.com/thammer/stomphacks/blob/26470497e7de90497fba7528386b8029b84f8939/docs/zd2-abi.md)
is TI C674x, float32 audio, 44,100 Hz, stereo blocks of 16 frames. A block spans
**362.8 microseconds**, shared with firmware and other active processing. We
have not established a measured cycle budget or processor clock for this unit.
The 270-unit `dspload` budget is declared metadata; it does not measure execution.
An x86 benchmark, successful compile or plausible MAC count cannot establish
on-pedal CPU utilization.

[Build rules](https://github.com/thammer/stomphacks/blob/26470497e7de90497fba7528386b8029b84f8939/docs/building-effects.md)
require a leaf kernel: no runtime calls, dynamic allocation, writable statics or
unresolved symbols. Our existing stack-enabled large kernels retain these
checks. The documented large-kernel `.text` budget is **16 KiB**; this is a
separate constraint from filesystem space. TI 8.3.15 offers C++14, whereas
Velvet's portable implementation requests C++17. Neither project is a drop-in
kernel: reuse the algorithms in the existing C adapter, force-inline helpers
and supply bounded arithmetic approximations where required.

After the final 34-effect readback there are **576,690 filesystem bytes free**.
Current custom binaries/icons total **510,685 bytes**. Runtime delay memory is
not stored as an audio asset in flash. Neither algorithm needs large impulse
response files. Storage therefore looks less restrictive than RAM/CPU, but
neither new C674x ZD2/ZIC pair has been built: exact size, section limits and
fit of both together remain unverified. The checked-in ARM firmware files are
not Zoom binaries and their sizes cannot predict ZD2 size.

## Dynamic Velvet Decorrelator

Inspected commit
[`a391a12a0b96b190a05cd7cefa25becf4f31660c`](https://github.com/115dkk/Velvet-Noise-Decorrelator-VST3/tree/a391a12a0b96b190a05cd7cefa25becf4f31660c).
Its [portable processor](https://github.com/115dkk/Velvet-Noise-Decorrelator-VST3/blob/a391a12a0b96b190a05cd7cefa25becf4f31660c/src/processor.cpp)
is independent of the VST3 wrapper: per-channel sparse FIRs, two tap banks and
one history ring per channel. Default length is 27.5625 ms, approximately 30
taps/channel. The UI permits 100 ms and 4,000 impulses/second, giving 400 active
taps/channel. Dynamic mode crossfades the old and new convolutions.

### RAM

At 44,100 Hz, default `prepare()` reserves for the maximum ranges even when
using the 30-tap default:

- Two rings: `2 × (ceil(44100 × .1) + 2)` = **8,824 samples**.
- Four tap banks: `4 × (ceil(.1 × 4000) + 2)` = **1,608 tap records**.
- With double samples and 16-byte `{uint32 delay, double gain}` records, the
  ring/tap payload alone is **96,320 bytes**, before object/allocator overhead.
- With float samples and eight-byte `{uint32 delay, float gain}` records,
  the same full reserved ranges need **48,160 bytes**, plus modest state.

Both fit the measured arena easily. The float layout is preferable for the
existing ABI and finite arena-reuse discipline. Indices/counters/seeds need
safe representation when another effect later reuses the arena; do not place
arbitrary raw integer or double bit patterns there without protection.
The [original data model](https://github.com/115dkk/Velvet-Noise-Decorrelator-VST3/blob/a391a12a0b96b190a05cd7cefa25becf4f31660c/include/velvet/processor.h)
uses vectors and a 64-bit deterministic seed; a port needs fixed-capacity arena
storage, not an STL heap.

### Processing

| Stereo configuration | Tap products/frame | Tap products/second at 44.1 kHz |
|---|---:|---:|
| Default 30 taps, one bank | 60 | 2,646,000 |
| Default, during transition | 120 | 5,292,000 |
| Maximum 400 taps, one bank | 800 | 35,280,000 |
| Maximum, during transition | 1,600 | 70,560,000 |

These are multiply/accumulate counts, **not measured CPU loads**. Random history
reads, wrapping, bank access and mixing add costs. The source computes sine and
cosine every transitioning frame, uses runtime integer modulo in the inner tap
loop, and performs powers, normalization and 64-bit random generation for an
entire future bank synchronously at a transition boundary. That burst can miss
a 16-frame deadline even if average convolution cost fits.

A practical port would preserve the default 30-tap region first, eliminate the
redundant modulo using validated delay bounds, use a bounded crossfade
recurrence/table, and prepare the next bank incrementally before it is needed.
Rapid parameter changes must not synchronously regenerate/clear everything in
one audio callback. Preserve deterministic seed/channel behavior and validate
float-vs-double impulse response, energy, cross-correlation and transition
continuity. The full 400-tap ceiling may need a lower density cap if target
profiling shows insufficient margin; RAM does not force that reduction.

The upstream portable core builds and its tests pass with assertions enabled
(Debug, VST3 disabled). The three test routines check block-size determinism,
normalization/decorrelation and smooth transitions. These are host tests only.
The source places setup calls inside `assert`, so Release/NDEBUG testing alone
would not establish the same result. License is **MIT**, with notices retained.

**Verdict:** likely feasible, and the better first candidate. No RAM or obvious
flash blocker for full stereo; full-range real-time CPU behavior is unproven.

## PlateauNEVersio / Campestria Versio

Inspected commit
[`4218b072e7420dd788cd3c98c36b3eba445f8886`](https://github.com/digitalartifactmusic/PlateauNEVersio/tree/4218b072e7420dd788cd3c98c36b3eba445f8886).
This is an embedded Daisy/Versio firmware port of Valley Plateau. Its
[application](https://github.com/digitalartifactmusic/PlateauNEVersio/blob/4218b072e7420dd788cd3c98c36b3eba445f8886/PlateauTest.cpp)
runs at **32 kHz**, 32-frame blocks, with maximum tank time scale 4, modulation
depth 16 and predelay up to four seconds. It includes eleven output gain/clip/
distortion modes and a linked limiter; those are additional to the reverb.

### RAM and direct-port problems

The [delay implementation](https://github.com/digitalartifactmusic/PlateauNEVersio/blob/4218b072e7420dd788cd3c98c36b3eba445f8886/dsp/delays/InterpDelay.cpp)
declares `float sdramData[50][144000]`: **28,800,000 bytes**, about **40.8×**
our verified arena. That rectangular reservation greatly exceeds the actual
13 live delay lengths, so it is not an algorithmic minimum.

A host layout probe compiled the original reverb classes with only the Daisy
section macro/includes stubbed. It did not process audio. After the same
sample-rate setup as the application, live logical delay lengths sum to
**320,269 float samples = 1,281,076 bytes**, still too much. This includes an
oversized **192,010-sample predelay**. Four seconds at the application's 32 kHz
actually requires 128,000 samples, reducing that compact buffer total to about
**1,025,044 bytes** with interpolation margin. This still exceeds the arena.

There is also a concrete source bounds mismatch: the predelay's logical
length is 192,010 but each physical array row has capacity 144,000. The source
increments a global row counter in constructors, including temporary objects
and repeated sample-rate initialization: the probe reaches row count 34 after
construction and 46 after the application's setup. These globals and allocation
semantics must be replaced, not carried into a pedal kernel. This is an offline
finding about the candidate, not a fault in our installed effects.

Using the source's conservative
[delay-length formulas](https://github.com/digitalartifactmusic/PlateauNEVersio/blob/4218b072e7420dd788cd3c98c36b3eba445f8886/Dattorro.cpp),
float32 histories, maximum size 4 and depth 16:

| Proposed internal rate | Maximum predelay | Delay buffers only |
|---|---:|---:|
| 32 kHz | 250 ms | 545,044 B |
| 32 kHz | 500 ms | 577,044 B |
| 32 kHz | 1 second | 641,044 B |
| 32 kHz | 4 seconds | 1,025,044 B — exceeds grant |
| 44.1 kHz | 250 ms | 808,480 B — exceeds grant |
| 44.1 kHz | 4 seconds | 1,469,980 B — exceeds grant |

The 44.1 kHz rows model a corrected sample-rate adaptation; changing the
application rate alone does not achieve it, because the tank currently clamps
to 32 kHz. Lengths include the four input diffusers, eight tank buffers and
predelay, but exclude state, guards, limiter and resampling.

The output limiter adds a
[32,000-float running-average array](https://github.com/digitalartifactmusic/PlateauNEVersio/blob/4218b072e7420dd788cd3c98c36b3eba445f8886/src/dsp/signal.hpp)
(**128,000 bytes**) and an 8,192-float amplifier table (**32,768 bytes**).
Its configured 300 ms window at 32 kHz uses only 9,600 entries: compacting that
array to **38,400 bytes** can preserve that window. It is one shared detector,
not two independent 128 KB channel detectors. Unused FFT/analyzer and other
library facilities should not be brought into the effect.

A credible first configuration is therefore **32 kHz internally, size 4,
250–500 ms predelay**, compact histories and the compact limiter. Buffer plus
compact-detector/table totals are **616,212–648,212 bytes**, leaving roughly
57–89 KB for scalar state, resampling, guards and any remaining tables. This
is a resource proposal, not a verified allocation or CPU result. Omitting or
replacing the output limiter would change behavior and must be explicit.

Another option is native 44.1 kHz with maximum size reduced to 2 and 250 ms
predelay: the original padded buffer formula yields **552,560 bytes**, before
limiter/state. Tighter individual bounds, based on every output tap and maximum
modulation excursion, could make better use of memory, but need independent
boundary tests rather than an unchecked reduction in allocation. Reducing the
internal rate further or reusing our 15-bit histories could preserve longer
predelay, with bandwidth/precision changes; long feedback/freeze tails make
those compromises particularly audible. Full four-second predelay plus size 4
at the original 32 kHz does not fit uncompressed float histories even with a
more economical per-line bound estimate (~919 KB before other state).

### Processing and integration

The reverb itself has **13 interpolating delay operations, eight allpasses,
four LFOs, one-pole filters and 14 output taps per sample**. This is a bounded
algorithm with no long convolution; a float C674x implementation is plausible.
The source uses double arithmetic extensively and processes control updates,
knob smoothing, LED/button logic and parameter setters at audio rate. Retain
necessary smoothing but move derived coefficients and hardware UI housekeeping
out of the sample loop. A 32 kHz internal port also needs a real anti-aliasing
sample-rate converter to/from the 44.1 kHz host; simply skipping samples is not
a valid conversion. Its state and CPU cost must be budgeted.

The input filters, changing delay times, near-unity feedback, freeze, buffer
clear and all output modes need native boundary/stability/reference tests before
hardware. The original README documents past startup and minimum-size bursts;
the Plus implementation needs our initialized-state guard, bounded incremental
clearing, finite arena storage, coefficient snapshots and guarded outputs.
It cannot copy the firmware's four-second startup hold as its memory-safety
strategy. The full inlined DSP plus eleven distortion modes may also hit the
16 KiB kernel budget; exact TI compilation remains necessary.

License: the main reverb is **GPL-3.0-or-later**, with separate third-party
notices. A derived port must retain its corresponding source/license notices
and cannot simply be relabeled MIT. No Daisy firmware flashing is involved in
a Zoom port; only a separately compiled, validated ZD2 would be considered.

**Verdict:** worthwhile as an adapted port of the reverb core. The original
firmware/storage model cannot be reused, and preserving all original ranges
and output modes is not yet supported by the resource evidence. Shorter
predelay is the most straightforward initial compromise.

## Evidence and next validation gates

Ignored local evidence is under `build/msplus/feasibility-20261031/`:
`RESOURCE-ACCOUNTING.json` pins source hashes and formulas; `accounting.py`
reproduces the figures; `plateau-layout.cpp`/`.txt` record the constructor/layout
probe; `velvet-debug-test.log` records assertion-enabled upstream tests. Both
clones are clean. No candidate code was installed on the pedal.

Before claiming either port works: compile a guarded leaf kernel through the
existing pinned Stomphacks pipeline, check exact `.text`/ELF/ZD2/ZIC sizes and
arena layout, compare against native reference DSP, then measure actual worst
case audio continuity on hardware. Include Velvet renewals/transitions and
Plateau minimum/maximum sizes, predelay changes, modulation, freeze and clear.
The current 34 effects can remain installed if the new validated pairs fit the
measured free space; simultaneous execution is a separate qualification.
