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
| Level | Output level; 50 matches folded loudness before the parallel-clean voice blend. |
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

Hardware qualification passed on firmware 1.10. The campaign contains 66
reviewed cases plus baseline, silence and restoration recordings (70 total),
covering 42 Drive/SYMM combinations, quiet/loud inputs, all 15 stage/voice
combinations, input-filter voice response, and calibrated harmonic comparisons.
The LOW voice reduced 4 kHz relative to 200 Hz by 25.74 dB. All 138 measurable
native/hardware harmonic comparisons passed unchanged tolerances: maximum
fundamental error 0.65 dB (limit 1 dB), higher-harmonic error 2.34 dB (limit
3 dB). All recordings were finite, without full-scale clipping or xruns.
Native validation passes 28 tests; 24 tooling/fault tests also pass.

The cable mapping had changed since the previous campaign. Both the archived
0.10 binary and this redesign responded to interface output 8, while the dry
stereo path remained output7→input3 and output8→input4. The known diagnostic's
997/1499 Hz outputs independently confirmed that DSP bus A now returns on
input 3 and bus B on input 4. The harness now recomputes mono routing from the
actual recorded dry WAVs, rejects ambiguous or inconsistent routes, and uses
that input for analysis. No DSP tolerance was relaxed.

A fresh, separately measured quiet bus-to-return calibration produced gains
1.3213659325 and 1.3159428166. The earlier calibration had the opposite channel
orientation; using it incorrectly failed one stage-three fundamental near a
sensitive fold position. Current calibration and source data are retained in
`build/msplus/wavefold-current-calibration-01/`; the original captures remain
unchanged in `build/msplus/wavefold-stages-hil-01/wavefold/hil/`.

The fresh pre-modification backup contains 374 CRC-verified files and all 100
stock-only saved patches. Tests restored the stock scratch patch and actual
stereo audio before removing each experimental/diagnostic pair. The accepted
WaveFold artifact is retained for manual audition. The final audit read back
all 68 installed files and rechecked stereo audio after closing file sessions.
The other 33 effect binaries and all 34 icons match their pre-modification
backup byte-for-byte. Exact evidence is
`build/msplus/wavefold-final-20261030-01/COMPLETE.json`.
Never save a patch that
contains experimental effects; autosave remains OFF.

Artwork changes are deferred. The existing icon pixels are retained.
