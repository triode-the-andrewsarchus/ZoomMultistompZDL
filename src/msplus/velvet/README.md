# Velvet — MS-70CDR+ port

Derived from 115dkk's MIT Dynamic Velvet Decorrelator, pinned at
`a391a12a0b96b190a05cd7cefa25becf4f31660c`. See LICENSE.

Default Input is mono L, feeding independent FIRs to both outputs. Mono R and
independent stereo are also available. Mix=0 uses the selected input routing;
bypass preserves the original stereo bus. Time is 0.1 ms/step (minimum 1 ms),
Dens is 4 impulses/second per step (minimum 100), Evol is 0.1 seconds/step,
XFade is milliseconds (limited to 90% of Evol), and Decay is attenuation in dB.
Var adds a deterministic integer to the original default seed. Mode selects
static or evolving kernels. Eight audible parameters plus input selection fit
on the Plus's parameter pages.

The source's default 27.5625 ms / 1088.435 impulses/s is quantized to the
pedal's integer controls: 27.6 ms / 1088 impulses/s, still 30 taps/channel.
Full 100 ms / 4000 impulses/s is retained. Samples/gains use float32; the
SplitMix64 generator retains its integer sequence, using its top 24 bits for
float jitter. Native reference tests cover tap placement and normalization.

A third bank prepares the future filter over bounded callbacks; the audible
transition remains the original two-bank equal-power crossfade. At most eight
taps are generated or 32 normalized per block, and initial arena clearing is
bounded to 256 words per block. Initial startup/parameter rebuild temporarily
passes the selected dry input while preparing all three banks; it does not
block the audio callback. Changing filter/timing/seed controls rebuilds the
kernels, while Mix, Mode and Input do not clear histories.

The first hardware pilot matched the default FIRs but failed dense FIR and
stereo-separation checks. Its source/artifact/captures remain archived; stock
audio and saved-bank restoration passed and that binary was removed. Version
0.11 uses mirrored histories and a tap-outer block FIR to reduce memory traffic,
retaining the full parameter range. Native upstream-reference/safety tests and
TI leaf validation pass. The fresh 0.11 hardware pilot passes all nine cases: maximum
band-response error is 0.360 dB against a 1 dB limit; fast dense mono-to-stereo
renewal has interchannel correlation 0.011; stereo leakage is below -40 dB.
No capture xruns, clipping, silence, renewal dropouts or zero-input growth were
detected. Stock audio and all 100 saved patches were restored before removal.
Evidence: `build/msplus/velvet-pilot-20261031-02/velvet/hil/`. Declared load 220 is conservative
composition gating, not measured CPU utilization. Never save an experiment.

The mirrored block-FIR layout requires 90,592 arena bytes on this build.
The kernel is 13,356 bytes before generated handlers; the unmodified upstream
validator accepts the leaf/stack, relocation, envelope and section checks.
Hardware qualification covers the reviewed standalone cases, not arbitrary
chains or every control sequence. Retained installation is tracked separately.
