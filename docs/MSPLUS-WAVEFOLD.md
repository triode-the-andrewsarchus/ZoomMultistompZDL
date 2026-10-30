# WaveFold redesign for MS-70CDR+

Version 0.11 replaces the original parallel threshold model with one to five
cascaded sine-folding cells. The default is five. Quiet signals now reach the
nonlinear range across SYMM instead of only near a few threshold offsets.
This is original Plus DSP, retaining attribution for Matujuice's MIT inverse
square-root method used by the output level matcher.

| Control | Behavior |
| --- | --- |
| Drive | Input gain and cell excitation; 0–100, default 40. |
| Symm | Alternating bias between cells, centered at 50. |
| Voice | LOW, FULL or BLEND; default FULL. |
| Tone | Post-folder low-pass; 100 is fully open. |
| Level | Output level, with 50 giving matched wet loudness. |
| Mix | Linear overall dry/wet blend; default 100. |
| Stages | 1–5 actual folding cells; default 5. |

VOICE follows the routing requested from Cosmodio Gravity Well's description;
it does not claim to reproduce that pedal's circuitry. LOW uses two input
low-pass poles, approximately 900 Hz each, before generating new harmonics.
FULL feeds the full input spectrum into the folder. BLEND combines 55% folded
signal with 45% aligned clean input, before Level and the independent Mix
control. Voice transitions are smoothed.

Stages is a discrete selector. It changes the number of cells evaluated, with
input trim `2^(5-N)` keeping lower stage counts useful at quieter levels. It
can change the waveform abruptly while playing. Each cell uses a wrapped,
degree-13 sine approximation. Algebraically composing five such polynomials
would have degree 371,293 even before accounting for the moving wrap regions
and bias. A bounded loop over at most five cells preserves the topology and
avoids evaluating unselected cells. The TI build verifies that the kernel
remains a leaf function with no runtime-library calls.

The nonlinear chain runs at four times the 44.1 kHz DSP rate. Cascaded half-band
FIR interpolation and decimation contribute 12 base-rate samples of delay
(0.272 ms); the internal clean path uses the same delay. This is the DSP
filter delay, not the complete interface/pedal latency. RMS matching prevents
Drive or stage count becoming merely an output-volume control. The arena
header retains the established packed-state protection against corrupting
stock audio when the effect is replaced.

Native tests cover all 101 SYMM values in all three voices at two input
levels and two Drive settings, every stage count against an independent
`sin()` reference, separate LOW/BLEND behavior, dry alignment, and protected
state/ABI invariants. A 3.1 kHz, Drive 70 test measures over 8 dB less alias
energy than an unoversampled independent sine cascade. This is a selected
aliasing test; high notes and extreme Drive can still alias.

Hardware qualification is in progress. The reviewed campaign covers 42
Drive/SYMM combinations, quiet/loud inputs, all 15 stage/voice combinations,
the input-filter voice response, and calibrated native harmonic comparisons.
Saved patches must remain stock-only and autosave must stay OFF.

Artwork changes are deferred. The existing icon pixels are retained.
