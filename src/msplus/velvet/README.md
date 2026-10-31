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

Current status: native upstream-reference/safety tests pass; TI leaf build
passes. Hardware qualification is pending. Declared load 220 is conservative
composition gating, not measured CPU utilization. Never save an experiment.
