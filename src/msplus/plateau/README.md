# Plateau / Campestria plate reverb — MS-70CDR+

Upstream: digitalartifactmusic/PlateauNEVersio,
`4218b072e7420dd788cd3c98c36b3eba445f8886`, based on Dale Johnson's
Valley Plateau / Dattorro reverb. GPL-3.0-or-later; retain the supplied licenses
and third-party notices. Hardware qualification is pending.

The port retains the original 32 kHz plate topology, maximum size 4, modulation
depth 16, diffusion, input/tank filters, input gain, freeze and clear. Predelay
is capped at the approved 500 ms. The output section uses the normal lookahead
limiter and a Level control. Per the requested scope, the upstream distortion
modes and additional Bogaudio dynamics processor are omitted.

## Controls

| Control | Behavior |
|---|---|
| Mix | Dry/wet blend, 0–1000. |
| Size | Original quadratic size curve, 0.01–4. |
| Decay | Original nonlinear feedback curve. |
| Pre | Predelay in milliseconds, 0–500. |
| Speed | Original modulation speed curve. |
| Depth | 0–255 display; original 0–16 modulation depth; edits shape while depth is locked. |
| Hold | RUN, FRZ, CLEAR; clear triggers once when selected. |
| Level | Output trim, 0–2×; 100 is unity, before the limiter. |
| Edit | Select INHI, INLO, TNKHI, TNKLO, DIFF, INAMP, LIMIT, SHAPE or LOCK. |
| Value | Edit the selected advanced setting, 0–1000. |

Changing Edit selects a target; only a subsequent Value movement changes it.
Other advanced settings are retained. Value displays the shared editing knob,
not a readout of all stored settings. Reinitializing the effect restores defaults.
LOCK captures the current depth; while locked, Depth adjusts modulation shape.
LIMIT lowers the limiter threshold; its default maximum is a DSP peak of 0.25,
below the rig's independently measured linear output range through 0.275.

The original smoothing recurrence advances at 32 kHz. Setters apply at the end
of each host block, avoiding repeated coefficient calculations in the audio
loop. Small endpoint snaps prevent float smoothing from stalling below full
freeze or above zero. Clear fades the reverb feed/output, clears histories in
bounded slices and fades back in while retaining settings.

## Build and memory

`tools/msplus/build.py plateau` uses the pinned Stomphacks compiler, packager,
container checks and native Plus artwork. The root manifest is the musical
candidate; `offline-core-probe` is a separate development identity, never for
installation. No firmware, factory effects or saved patches are modified.

The current candidate passes the unchanged target validator: **17,152 bytes of
text**, under the **18,432-byte** ten-control cap; only accepted relocations,
no runtime helper calls and no writable static storage. The TI compiler's layout
measurement reports **602,240 arena bytes required**, including the encoded
control header, versus the verified standalone **705,600-byte** grant. Multi-slot
arena sharing and CPU headroom remain unqualified.

Histories initialize cooperatively (at most 1,024 core and 1,024 limiter words
per callback). Integer/control state is encoded between callbacks; raw header
words are erased. Non-audio limiter histories and pre-limiter audio are stored
at very small scales so firmware reusing the arena does not interpret control
sums or amplified samples as loud audio. An unstable core output is quarantined
and cleared; native tests require its fault counter to remain zero.

The 64-tap, 32-phase rational SRC converts 44.1 ↔ 32 kHz. Its readonly tables
use Stomphacks' existing `const_blob` support, retaining the parameter table's
required position. `resample_coeffs.py` reproduces them. `plateau_derive.py`
mechanically derives the float core; it shares symmetric arithmetic and pole
coefficient storage while retaining each channel's operation order.

## Verification and safe use

Six core profiles compare against the pinned upstream double DSP: impulse tails,
minimum/maximum size, 500 ms predelay, extreme modulation and independent filters.
The explicit target initializer is tested from poisoned storage without an
extra signal-state clear. AddressSanitizer and UndefinedBehaviorSanitizer cover
extreme core and limiter profiles. Four control tests cover endpoints, retained
advanced settings, depth lock, freeze and clear edges. Whole-adapter tests cover
latency/gain/isolation, stereo tails, live controls, clear, invalid coefficients,
insufficient arena grants, canaries and encoded-header cleanup.

Run `python -m unittest discover -s tools/msplus -p 'test_plateau*.py' -v` in the
project venv. Separate SRC tests verify exact rate accounting, unity DC,
under 0.03 dB round-trip gain error through 12 kHz, channel isolation and more
than 65 dB rejection at tested 16–21 kHz tones. These are software/component
checks; actual hardware measurements and stock-audio restoration are still
required before retention.

The HIL campaign uses reviewed cases in `plateau_reference.py`: dry path,
calibrated limiting, native plate transfer responses, predelay, level, damping,
maximum modulation, freeze and noise-floor clearing. It uses the existing
safe installer, dry runs, exact readback, temporary-patch guard and independent
stock-audio restoration gate. Autosave must remain OFF. Never save this effect
into a patch.

Generated C++ compatibility headers adapt TI's inline syntax locally, preserving
shared C headers and all 35 previously qualified effects' source fingerprints.
Historical build logs and the earlier complete upstream distortion implementation
remain in git history; their size limits do not describe this plate-only build.

Architecture comparison against `pre-velvet-plateau` reports duplication growth
(10.59% to 11.69%). This includes the retained historical HIL journal, mandatory
license copies, generated TI C++ compatibility copies and the explicit offline
fixture manifest. The fixture includes the production kernel rather than copying
it. The adapter callback's CCN 18 reflects its fail-closed coefficient, arena and
state checks plus bounded stereo/SRC processing; those checks remain required.
Control editing, smoothing and filter coefficient updates are separate cohesive
operations. Existing installer, capture, native kernel and analysis mechanisms
are reused; no alternate hardware transport or effect packager was added.

The first hardware pilot stopped before its first effect capture: the Level
knob was specified as 0–1000 in EDTB's 8-bit eighth parameter slot; readback was
244 for 500. Depth uses another 8-bit slot. Their display scales are now 0–200
(Level, unity 100) and 0–255 (Depth); normalized DSP ranges are unchanged.
Build and audition guards reject values exceeding the patch format's width.
During checked cleanup, direct replacement returned the missing-effect ID;
loading the already-verified stock patch using the documented Plus bank/program
messages restored the exact stock settings and healthy stereo audio. All 100
saved patches remained unchanged and the first binary was safely uninstalled.
Evidence: `build/msplus/plateau-pilot-20261031-01`,
`build/msplus/plateau-stock-reload-20261031-01`. This pilot does not qualify the
DSP; a complete repeat with corrected ranges is required.
