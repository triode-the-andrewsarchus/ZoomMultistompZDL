# MS-70CDR+ development

Experimental ports on branch `feat/ms70cdr-plus`, tested on an actual MS-70CDR+
firmware **1.10**. All **22 original musical effects** and **12 Matujuice v1.5
effects** now build as ZD2 and pass selected standalone hardware checks. All 34
are installed with adapted original artwork for manual audition. The retained-set audit read
back all 68 files, confirmed all 100 saved patches unchanged, preserved factory
catalogue entries and verified stock stereo audio with autosave OFF. The exact
latest WaveFold installation evidence is `build/msplus/wavefold-final-20261030-01/COMPLETE.json`.
The earlier artwork installation evidence is `build/msplus/artwork-final-20261029-01/COMPLETE.json`.
The earlier DSP retention audit is `build/msplus/retained-34-20261029-01/`. A fresh full
readback verified all 305 original files except the deliberately updated effect
list byte-for-byte, including all 302 factory effect/icon/IR files. The final
post-readback stereo audio check also passed. See
`build/msplus/final-audit-34-20261029-01/COMPLETE.json`.
Released `dist/*.ZDL` files and the browser editor still target the original
pedals. No Plus release binaries have been published.

## Port inventory and validation

The original 22 are Flower, Klang, Scorch, Corrupt, Howl, Dustbox, GenLoss,
Microlm, Shatter, Arrakis, Taffy, Dissolve, Mangle, Rooms, Hydra, Spiral,
Stasis, Rewire, Gyre, Galactic, Spool and Oxide. All have run
individually on this pedal with finite recordings, no ADC full-scale clipping and
no xruns at selected
settings. Spiral passed its first pedal test on October 29.
A stricter activity check found that Rewire's default bit crusher silences the
very quiet test input; its test profile now lowers Bits without changing its
musical defaults. Rooms DIGIT/GATE needed threshold-aware test settings: the native
reference confirms that Time=100, Depth=0 and the existing -20 dBFS send ceiling
produce measurable output. Neither source defaults nor safety limits changed.
The reviewed Rewire/Rooms reruns passed on October 29.

Matujuice adds WaveFold, DualShft, Choral, EuGate, DubSiren, S.GN_L, Scrub,
GridDly, SyncEQ, Breather, DirtBox and Sweep. Their pristine MIT-licensed C DSP
cores come from the pinned v1.5 dependency; the repository contains only Plus
adapters and its license, with one exception: WaveFold 0.11 now has a
[Plus-specific DSP redesign](MSPLUS-WAVEFOLD.md), configurable 1–5 stages and
LOW/FULL/BLEND voices. Two eight-sample calls per Plus callback preserve
source clock cadence. Active output is mono from physical left input, copied
to both outputs, matching the original mono DSP path. Ordinary bypass retains
stereo. DubSiren and GridDly retain their own bypass/tail logic.

The legacy dry-buffer tempo-tag transport has **no verified Plus mapping**.
Adapters use its supported no-tag path. Local tempo and twin-tempo changes are
retained; cross-effect FOLLOW/Mozaic tempo relay is not implemented. Numeric
parameter controls are provided; original artwork is adapted to Plus icons.
Custom value labels remain deferred.

Native checks cover all 34 kernels, invalid coefficients, initialization and
arena canaries, selected control extremes, original-versus-Plus sample math,
and independent references for several simpler effects. Hardware checks also
include Klang sidebands, Corrupt sub/master/harmony, Stasis capture/hold while
bypassed/release, and selected Matujuice signatures. Scorch now passes its
calibrated maximum-Gain comparison inside the independently measured output
linear range. Fundamental errors are -0.044/-0.021 dB; compared harmonics differ
by at most 1.24 dB, within the unchanged tolerances. Its high-output capture still
shows the separately measured output-chain compression and remains explicitly
outside the direct linear reference comparison.

These checks qualify selected standalone cases, not all knob transitions,
long-duration endurance, every source feature or multi-effect chains.

The [current evidence report](MSPLUS-HIL-34.json) records the latest per-port
status as of October 30. Previous snapshots remain in Git history.
`tools/msplus/report.py` refreshes it from explicitly ordered campaign directories,
reusing the installer's actual measurement, restoration and source/binary gates.
An incomplete or failed newer attempt supersedes an older pass. Test counts come
from passing unittest logs, whose hashes are recorded. It opens no pedal or audio
connection; supplying the same path for `--previous` and `--output` is supported.

```sh
$PY tools/msplus/report.py --previous docs/MSPLUS-HIL-34.json \
  --output docs/MSPLUS-HIL-34.json \
  --native-log build/msplus/native-rng-pcm15-all-01.log \
  --tools-log build/msplus/tools-scorch-linear-03.log \
  build/msplus/matu-packed-campaign-01 \
  build/msplus/remaining-ports-campaign-20261029-03 \
  build/msplus/remaining-ports-campaign-20261029-04
```

**34 effects** pass selected standalone hardware checks. SyncEQ and DubSiren now
pass actual stock-audio restoration with protected control-state storage. All ten
Matujuice ports tested in `matu-packed-campaign-01` passed and were removed safely.
Scrub and GridDly subsequently passed hardware tests with full-length, 15-bit
histories; see the precision note below. Scorch passed after separating DSP
comparison from independently measured high-level output compression.
All 34 have current binary/source provenance and verified stock-audio restoration;
the accepted campaigns contain 333 recordings, including the redesigned
WaveFold's 70. The complete set is now retained.

### Original artwork on Plus

All 34 original title/illustration panels are preserved in
[`src/msplus/artwork`](../src/msplus/artwork/README.md). The Plus build adapts
them into its 72×97 browser and 102×128 edit icons, retaining the original
pixel art rather than the temporary text-only placeholders. The old knob row
is excluded because the Plus renders its controls separately. Artwork updates
change only the embedded ICON pixels, companion ZIC and required CRC; DSP,
parameters and identities remain byte-identical to their tested versions.

`tools/msplus/artwork.py` repackages existing builds offline and also runs after
normal builds. Qualification checks the variant against the exact archived
hardware-tested binary, allowing only ICON/CRC changes and requiring the ZIC
to match the current source artwork. It retains the original hardware evidence
and records the artwork variant separately; it does not claim that these
new containers were the binaries used in the earlier DSP captures.

All 34 artwork pairs are now installed. A fresh pre-update backup verified 374
files and 100 stock-only saved patches; all 305 original non-catalogue files
matched the original backup. The guarded replacement campaign used upstream
dry runs, uninstall-before-install and readback verification. Stasis uses its
bottom artwork panel because its original knobs sit above the illustration;
an additional crop test checks all 34 sources against the original live value
box positions and their recorded source hashes.

The final audit read back all 68 current files byte-for-byte, preserved the
factory catalogue and all 100 saved patches, and independently verified that
every new ZD2 differs from its backed-up predecessor only in ICON and CRC.
WaveFold also passed its selected hardware cases with the updated container
and verified stock-audio restoration (`build/msplus/artwork-smoke-01/`). After
the complete-set readback closed its file sessions, both stereo loopback paths
passed again (correlations 0.952/0.951, gain -20.13/-20.07 dB). Autosave is OFF,
the temporary patch is stock-only, PipeWire quantum is restored to 128, and
580,780 bytes remain free. The final proof binds the catalogue/file audit,
audio recording, source-to-container equivalence and accepted hardware report:
`build/msplus/artwork-final-20261029-01/COMPLETE.json`.
See the [34-effect artwork preview](images/msplus-artwork.png).

### Historical WaveFold 0.10 input sensitivity

This diagnosis applies to the original port, superseded by the
[0.11 redesign](MSPLUS-WAVEFOLD.md). The new configurable cascade and voices
have separate native and hardware qualification.

Manual audition exposed a gap in the selected hardware checks: the WaveFold
test used SYMM 95, which lies exactly on a folding threshold. That check does
not establish audible folding throughout the SYMM range at quiet input levels.
The pristine Matujuice algorithm has straight transfer sections between its
thresholds. SYMM adds a DC offset; the DC blocker removes that offset, and
automatic level matching makes a straight section sound close to the original
signal (sometimes with inverted polarity). Input amplitude times Drive must
cross a threshold to produce pronounced folding. This behavior is preserved
by the Plus port.

A native sweep of every integer SYMM value, with Tone 100, Level 50 and Mix 100,
reproduced this behavior. At DSP input peak 0.0025 and Drive 37, only SYMM
5, 35, 65 and 95 exceeded 1% harmonic distortion. At input peak 0.05 and
Drive 100, all 101 values exceeded 1%. These are internal DSP amplitudes,
not interface output settings. All 202 cases matched the unprotected original
DSP core bit for bit, recorded in
`build/msplus/wavefold-symm-native-01.json`. This was native evidence, not an
additional hardware sweep. No binary or gain scaling changed at that stage.
The original test is retained in Git history; the current tests exercise the
redesigned stages and voices instead.

Those quiet-input gaps motivated the replacement DSP. The interface's return
gain remains downstream of the effect and cannot increase folding.

## Verified restoration fix and remaining history adapters

After the USB-079 restart, a healthy stock preflight permitted removing the old
SyncEQ artifact. The packed-state build then passed all configured audio checks,
stock stereo restoration and guarded removal (`synceq-packed-hil-01`). It repeated
successfully in `matu-packed-campaign-01`. DubSiren, Breather, all seven DirtBox
models, all eight Sweep modes, WaveFold, DualShft, Choral, EuGate and S.GN_L also
passed that campaign, with positive stock-audio recordings and unchanged saved
patches after each effect. Their control headers use the same lossless helper;
Choral packs four small regions around its audio arrays to avoid copying its
large CANON history. The pristine dependency remains unchanged.

The native arena inventory also found raw RNG words in GenLoss and Mangle that
can represent NaN. Their Plus branches now retain those integers in a reserved
small-state word and leave zero in the corresponding arena word between calls.
Native comparison against the original eight-frame kernels still passes; their
non-Plus `.audio` machine code is byte-identical (3,360/2,720 bytes), recorded in
`build/msplus/rng-legacy-preservation-01/results.json`.

Scrub and GridDly store two PCM samples per word; protecting only their headers
would still leave many non-finite float patterns in their histories. Their new
adapter preserves all 348,000 samples (7.9 seconds) using two signed 15-bit samples
encoded as tiny finite floats below 1.1e-19. **History precision is 15 bits instead
of the original 16**, with at most one original PCM count of error per write.
The cores use Q14 scaling, so that is at most 1/16384 in DSP amplitude; feedback
can accumulate quantization error. They are not bit-identical audio ports.
No delay range or control is removed. The generator changes only two read sites
and one write site in derived copies, refuses unexpected source layouts, and
never modifies the pinned upstream source. Derived code and generator hashes
are included in hardware provenance. Both generated effects pass upstream build
validation. Exhaustive PCM values, clean-wet reference error, full-arena finiteness,
canaries and all other native checks pass. With the redesigned WaveFold,
stage/voice and routing fault coverage, the current total is **28 DSP tests
and 24 tooling tests**.
Both ports passed hardware checks and stock restoration in
`remaining-ports-campaign-20261029-04`. Scrub's held-audio test explicitly selects
Rec=HOLD after recording; an earlier LIVE-mode test correctly failed when silence
overwrote the history. GenLoss and Mangle passed with their protected RNG storage
in `remaining-ports-campaign-20261029-03`.

The output-linearity diagnostic was safely removed after its completed campaign.
It measured less than 0.053 dB gain change through DSP peak 0.275, then
1.48/1.12 dB compression at peak 0.55. Its strict 0.5 dB linearity check correctly
fails. This identified a confounder in Scorch's high-amplitude comparison and
motivated the independently bounded comparison below; it did not justify relaxing
the DSP comparison tolerances.

The prepared Scorch comparison retains maximum Gain and the existing wet-only
high-level capture, and adds Mix=50 for a direct DSP comparison below the measured
output limit. `--output-probe` verifies the independent probe's restored-audio
proof, recording integrity and agreement with calibration, then derives the
contiguous range within 0.1 dB of quiet gain. High-level harmonic measurements
remain visible and explicitly marked outside that range; they are not described
as equivalent. The extra maximum-Gain capture must actually lie within the range
and pass the unchanged 1 dB fundamental / 3 dB harmonic tolerances. Missing or
out-of-range reference captures fail. Synthetic tests detect a deliberately
incorrect low-level DSP output and reject a changed calibration. Scorch passed
the actual `scorch-linear-range-hil-01` campaign, including stock restoration and
removal before the retained-set install. Trial edits are recorded in `CASES.json`.

`audit-after-packed-matu-01/VERIFIED.json` verifies an empty experimental set,
byte-identical factory effect list, all saved patches unchanged and autosave OFF
after that campaign. The next serialized campaign covers the remaining original
effects plus the two PCM-history ports. No firmware or recovery commands are used.

## October 29 restoration investigation (historical sequence)

A physical power cycle re-enumerated the pedal as USB device 075. The full audit
confirmed the factory catalogue and all saved patches unchanged. Both stock
stereo paths recovered at approximately -20 dB gain and 0.957 correlation. A
capture taken during file auditing was interrupted; audio capture and pedal-file
operations must be serialized, including read-only file operations.

Spiral and the threshold-adjusted Rewire passed, including actual stereo audio
after stock restoration. Rooms passed all six modes at the reviewed settings.
An xrun invalidated only its post-restoration recording; the runner stopped before
removal. A separate complete stock preflight then passed, and the original failed
recording was retained. Rooms was removed only after this independent positive
audio verification. S.GN_L subsequently passed its complete campaign and removal.

SyncEQ passed default/boost/cut and zero-input checks, then returned only noise
after stock metadata restoration. The runner caught this **before uninstall** and
left the binary available. Re-enabling stock, reselecting SyncEQ, and toggling
bypass did not restore audio. USB power management remained on/active. This rules
out deletion of the custom file as a necessary trigger; it does not yet establish
the DSP failure's cause. All diagnostic edits were temporary and documented MIDI.

The next physical restart re-enumerated the pedal as USB device 076. Stock audio
again passed both stereo paths (-20.08/-20.02 dB, correlation 0.958/0.957). The
`synceq-bypassed-transition-01` audition confirmed that the active EQ still passed
live input **after** the zero-input test: its filtered sweep had -19.81/-19.74 dB
gain and correlation 0.625/0.626. Thus silence processing alone did not cause
this failure. Restoration then bypassed the experiment and waited 250 ms before
replacing its ID. Stock audio still disappeared, without xruns or clipping and
before any removal. Bypass-first replacement is **not a demonstrated fix**.
The exact failing step and underlying cause remain unknown. SyncEQ remains
unqualified and installed; there is no `AUDIO_RESTORED` marker.

SyncEQ and DubSiren now also record immediately after bypass, before replacement,
to distinguish those two steps on the next run. This reuses the existing capture
and temporary on/off edit; it changes no DSP code or file-transfer procedure.
The independent post-restoration audio gate remains mandatory. The failure must
be understood before these effects can be retained for manual audition.

Another restart (USB 077) and the `synceq-bypass-boundary-01` run narrowed this
further: the bypassed custom effect passed both physical stereo paths at
-20.08/-20.02 dB with correlation 0.958/0.957, no xruns and no clipping. Audio
failed later during restoration. The optional `audition.py --trace-restoration`
now records after bypass, stock ID replacement, each restored stock knob, final
settings and editor exit. It adds no MIDI commands. Recording exceptions are
reported without interrupting stock restoration. This is diagnostic machinery,
not a DSP fix or evidence that effect replacement is safe.

The fresh storage audit is `build/msplus/audit-synceq-bypass-boundary-01/VERIFIED.json`:
autosave OFF, all 100 saved patches unchanged, all factory catalogue entries intact,
and exactly one valid custom binary/icon, SyncEQ, byte-identical to its build.
At that point the patch metadata was stock-only and file sessions closed cleanly.
A further physical restart was needed to resume audio testing; no firmware,
bootloader or undocumented recovery commands were attempted.

The USB-078 step trace subsequently isolated audio loss to the stock-ID edit,
before any stock knob was restored. The initial SyncEQ candidate used lossless
packed control-state storage between callbacks to keep NaN integer sentinels out
of reused audio memory. It passed 19 native tests and a bit-identical 114,688-sample
comparison with the earlier wrapper before the successful hardware runs above.
See [the memory investigation](MSPLUS-MEMORY-RESEARCH.md#stock-replacement-and-non-audio-arena-state-october-29)
for the hypothesis, exact storage layout, evidence and remaining PCM-ring concern.
Only SyncEQ opted in at that stage; the other ports were protected subsequently.

`install_set.py` prepares the requested final manual-audition set, but refuses
before any pedal operations until every musical port has passing required audio
checks, a valid stock baseline, verified stock-audio restoration, and current
binary/source hashes matching its exact hardware evidence. Restoration markers
link to the actual gain/correlation report and recording by SHA-256; a marker
without intact, passing audio evidence is insufficient. It reuses upstream
classification/install/readback, validates all artifacts before the first write,
then audits the entire retained set and stock audio. Sixteen offline
measurement/safety tests cover these gates and stopping on uncertain transfers.
The complete retained-set run is `build/msplus/retained-34-20261029-01/`.
Its `INSTALLED.json`, `audit/VERIFIED.json` and final stock-audio recording verify
34 installed musical ports, 68 byte-identical binaries/icons, all saved patches
unchanged, all diagnostics absent, stock scratch and autosave OFF.

The latest storage audit reports 1,190,190 bytes available with SyncEQ installed.
All 34 current ZD2/ZIC pairs total 499,073 bytes, so their file sizes fit within
the reported free space without removing factory effects. Filesystem allocation
overhead and final installation still need verification. This says nothing about
how many effects can run simultaneously; declared DSP loads and six chain slots
remain separate constraints.

## October 28 bench incident and initial continuation

After the first DubSiren campaign's restoration/removal, its repeat campaign
recorded a siren-like transient during what should have been a stock baseline,
then only ADC noise, including during live test input. MIDI remained responsive,
reported the original bypassed CloneCho, and accepted ordinary edits. The cause
is unresolved; this is an observation, not a diagnosis of a kernel crash.

The guarded uninstaller completed without transfer errors. A subsequent audit
confirmed autosave OFF, all 100 saved patches unchanged, the factory effect list
byte-identical, and **no experimental files installed**. [Documented stock patch selection](https://github.com/thammer/zoom-explorer/blob/main/src/ZoomDevice.ts)
(including selecting away and back) did not restore audio. No firmware,
bootloader, rescue or undocumented reset operations were attempted. A physical
power cycle has been requested only after the clean-storage audit.

The harness now requires correlated stereo audio at the calibrated gain before
installation and before custom-ID selection. After restoring the stock metadata,
it records another stereo sweep and requires `AUDIO_RESTORED` before uninstalling.
If that check fails, the runner stops with the binary still installed; inspect
logs and storage safety before further actions. Finite ADC noise is insufficient
for passing. Sixteen offline measurement/safety tests include invalid/noisy baselines,
catalogue changes, corrupted readbacks, and refusal to uninstall after metadata-only
restoration. Saved-patch dumps alone do not prove that stock DSP is running.

After the physical restart, verify identity/autosave, stock MIDI state **and real
stereo loopback** before resuming the pending ports. Investigate the DubSiren
transition separately before attempting to leave it installed. Keep the accepted
capture artifacts; do not promote build-only ports to hardware-qualified status.

## Delay memory and capacity

Stock-code analysis and quiet **read-only descriptor telemetry** established
`instance[3]` as `{base, exclusive_end, byte_count}` on this firmware. The observed
standalone grant is **705600 bytes**. The shared compatibility layer checks
alignment, range consistency and required size before dereferencing effect-owned
memory, never changes descriptor fields, and initializes only its own arena.
See [memory evidence and limits](MSPLUS-MEMORY-RESEARCH.md). Hydra and Stasis
clear large buffers in bounded steps.

The 34 ZD2/ZIC pairs total **510,813 bytes** with WaveFold 0.11. They are all
installed alongside the factory set, with **576,690 bytes free** after filesystem allocation. Capacity
to retain all 34 is therefore hardware-verified. Simultaneous processing has
separate limits: the pedal has
six effect slots, DSP loads are conservative placeholders, and multi-slot arena
ownership/aggregate CPU capacity have not yet been hardware-qualified. Start
manual testing with one custom effect at a time.

## Build with upstream tooling

[Stomphacks](https://github.com/thammer/stomphacks) supplies the compiler driver,
cleanroom scaffold, ZD2/ZIC packaging, validation and guarded installer. Read its
[SAFETY.md](https://github.com/thammer/stomphacks/blob/main/SAFETY.md),
[DSP ABI](https://github.com/thammer/stomphacks/blob/main/docs/zd2-abi.md) and
installation instructions before hardware work. `tools/msplus/upstream.lock.json`
pins Stomphacks, zoom-zt2 (including its directory-enumeration fix, PR 112),
and [Luca Matturro's Matujuice v1.5](https://github.com/matujuice/zoom-ms-zdl-effects-pack).
Setup never opens MIDI and refuses to overwrite an existing dependency tree.

```sh
tools/msplus/setup.sh
# Install TI C6000 tools separately; do not commit proprietary tools.
export ZOOM_TI_CGT=/path/to/ti-cgt-c6000_8.3.15
PY=build/msplus/venv/bin/python
SH=build/msplus/stomphacks
$PY tools/msplus/build.py
# Or select ports: $PY tools/msplus/build.py gain flower klang
$PY "$SH/tools-pedal/install_selftest.py"
$PY tools/msplus/test_dsp.py
$PY -c "import sys; sys.path.insert(0,'tools/msplus'); import upstream; import unittest; unittest.main(module='test_tools')"
```

The default compiler location is `build/msplus/ti/ti-cgt-c6000_8.3.15`.
TI 8.3.15 passes every upstream build REPORT check. Upstream documents 8.5.0
and tests firmware 1.20; these differences are recorded, not assumed equivalent.
Our audition tool deliberately accepts only the verified firmware 1.10 identity.

## Reusing original C

The original ABI uses 8-frame channel blocks, one context, a magic shuttle and
an arena descriptor. Plus uses 16 frames/channel, separate instance/context,
in-place audio at `ctx[1]`, normalized coefficients at `instance[1]`, and small
zeroed state at `instance[2]`. Thin source adapters include the original C with
`ZOOM_MSPLUS`; sample math is shared. Do not copy old proprietary handler blobs.

`src/msplus/common/compat.h` checks initialization and normalized parameter
snapshots, sanitizes inputs, implements firmware bypass mixing and rejects
non-finite/out-of-bounds outputs. The shared arena adapter bounds every grant before use; no dynamic allocation
or fixed DSP address is used. All 22 modified legacy kernels retain byte-identical legacy `.audio`
sections when built with the same TI compiler. Sixteen buffered ports also
match the original eight-frame C in native sample tests after initialization.

Gain drops the old 8x compensation for an uninitialized legacy handler.
Howl/Dustbox skip their legacy parameter-latch workaround. Corrupt's Plus
crossing counter saturates after one second to prevent signed overflow during
long silence. Its additional Gate knob scales the original 0.01 tracking gate;
default 100 preserves the original threshold. The weak interface loopback test
uses Gate=10 to exercise tracking. Other musical defaults match the originals.

Gain, Flower and the quiet calibration diagnostic use the strict no-stack
`.audio` route. Larger ports use Stomphacks' documented `kernel_section: text`,
`allow_stack: true`, `opt_for_space: null` mode. The verifier still prohibits
calls and unresolved runtime helpers. No upstream safety checks were patched.
Declared DSP loads are conservative placeholders; they are not timing profiles.

## Backup and guarded hardware campaign

Only one process may use MIDI. Autosave must be OFF with a pedal ACK. Never save
an experimental effect in a patch, overwrite/delete factory effects, flash
firmware, or issue unknown SysEx. Recovery from storage corruption is unproven.
Private playground IDs `07001100` through `07001280` cover the original ports
and diagnostics; `07001300` through `070013b0` cover Matujuice. Filenames start
with `XXZ`/`XXM`. Upstream collision checks remain mandatory; these are not public
ID allocations.

```sh
$PY "$SH/tools-pedal/safe_connect.py" build/msplus/session-YYYYMMDD
$PY tools/msplus/backup.py build/msplus/backup-YYYYMMDD
# Requires a one-slot, bypassed stock-only scratch patch and healthy loopback.
pw-jack $PY tools/msplus/run.py \
  --backup build/msplus/backup-YYYYMMDD --output build/msplus/campaign-01 \
  gain flower klang corrupt howl dustbox
# Scorch can run separately; calibration enables its stricter comparison below.
$PY tools/msplus/verify.py build/msplus/backup-YYYYMMDD build/msplus/final-audit-01
```

Backup uses upstream's completeness-gated enumeration and timeout-bounded,
CRC-checking FileSession downloads. It validates ZD2/ZIC envelopes, all 100
saved patches and the stock-only scratch patch; `VERIFIED.json` contains hashes.
A directory without that marker is incomplete. Files, patches, toolchains and
recordings stay ignored under `build/msplus/`.

The runner performs upstream install dry run, guarded install, audition,
verified stock restoration, uninstall dry run, guarded uninstall and analysis.
Audition independently reads back the installed binary and every parameter
edit. It checks saved patches before and after; ordinary audio failures still
restore the stock scratch patch before removal. Uncertain transfers or missing
restoration markers stop without follow-up commands. Keep the pedal powered
and inspect logs if protocol safety is unverified. The tool never retries an
uncertain write or blindly resets the pedal.

Patch dumps have 848-byte envelopes with variable padding beyond the PTCF's
declared length. Compare all defined PTCF bytes; retain raw dumps and CRCs.
Known unsolicited notifications are drained before fresh requests; unrelated
or error replies stop further edits. The audition transmitter allowlist permits
only reviewed temporary parameter/volume edits, never patch saves or file writes.

## Audio routing and measurement

The AudioFuse 16Rig presents 34 channels at 48 kHz. Physical discovery and
low-level independent probes established this mapping:

| Physical connection | JACK port |
|---|---|
| Output 7 to pedal input | `AF16Rig Audio Pro:playback_AUX6` |
| Output 8 to pedal input | `AF16Rig Audio Pro:playback_AUX7` |
| Pedal return to input 3 | `AF16Rig Audio Pro:capture_AUX2` |
| Pedal return to input 4 | `AF16Rig Audio Pro:capture_AUX3` |

The original measurements mapped DSP bus B to input 3 and bus A to input 4.
After the subsequent manual audition, a fresh distinct-tone diagnostic mapped
bus A (997 Hz) to input 3 and bus B (1499 Hz) to input 4. Both the archived and
redesigned mono WaveFold then followed interface output 8. The external dry
paths remain output7→input3 and output8→input4. WaveFold analysis now verifies
the actual mono route from recorded dry probes rather than assuming the
earlier cable orientation.

```sh
pw-jack $PY tools/msplus/audio.py build/msplus/probe-01 \
  --send 'AF16Rig Audio Pro:playback_AUX6' 'AF16Rig Audio Pro:playback_AUX7'
```

Default send peak is -50 dBFS; discover returns before raising it. The CLI
captures all physical AudioFuse inputs unless specified. No default speaker
connections are made. Deterministic broadband probes, logarithmic sweeps,
997 Hz tones and silence produce FLOAT WAVs and reports containing exact ports,
levels, block sizes, xruns, finite/clipping/silence checks, gain and latency.
Analysis reports band response, harmonics 2–5 and selected effect properties.
Pure tones cannot determine unambiguous latency; use broadband probes.

Campaigns keep one JACK stream open, sending zeros between captures. They
request PipeWire quantum 1024 temporarily, restore the previous forced quantum
(128 here), and preserve an intervening user change. Any xrun during recording
invalidates that capture. Measured loop latency around 71 ms includes host
buffering, both interfaces and the pedal; it is not intrinsic pedal latency.

Final tests use return gains **0 dB**, sends -30 dBFS except Corrupt tracking
and the reviewed Rooms DIGIT/GATE profiles at -20 dBFS. Earlier +12 dB return trials clipped on loud effects and were
rejected. A quiet bounded triangle diagnostic measured the return change as
-12.001/-12.001 dB. Do not change return gains mid-campaign.

## Scorch calibration and output-chain compression

The quiet diagnostic emits known triangles (997/1499 Hz, DSP peak at most 0.001),
using verified small state. `reference.py` estimates DSP-bus-to-return scaling,
then compares hardware harmonics against the actual C kernel compiled natively.
The stock-bypass tone supplies the input amplitude. Jointly fitting ten harmonics
plus DC avoids leakage into weak harmonics at arbitrary capture phases.

```sh
$PY tools/msplus/reference.py build/msplus/calibrate-hil-0db
$PY tools/msplus/analyze.py build/msplus/scorch-linear-range-hil-01/scorch/hil \
  --effect scorch --calibration build/msplus/calibrate-hil-0db/calibration.json \
  --output-probe build/msplus/matu-packed-campaign-01/linearity/hil
# run.py accepts the same --calibration and --output-probe options.
```

The initial Mix=100 comparison had a -1.5 dB fundamental error and a -3.5 dB
fourth-harmonic error. Correcting the estimator alone did not pass it. The bounded
`linearity` diagnostic then independently measured the output chain: gain changes
stay below 0.053 dB through DSP peak 0.275, but reach -1.48/-1.12 dB at peak 0.55.
Its strict 0.5 dB linearity test correctly reports failure. The diagnostic was
removed safely and is absent from the retained musical set.

The final Scorch test keeps Gain=100 and records both Mix=100 and Mix=50. The
latter's predicted DSP peaks are 0.2728/0.2724, within the independently measured
0.275 linear limit. Its fundamental errors are -0.044/-0.021 dB and all compared
harmonics fall within 1.24 dB. It passes the unchanged 1 dB fundamental / 3 dB
harmonic tolerances and noise threshold. The Mix=100 harmonic measurements remain
in the report, explicitly outside the measured linear range; they are not claimed
to match a linear output model. Missing, invalid or out-of-range calibration and
reference recordings fail qualification. No Scorch DSP math or acceptance
tolerance was changed. Actual audio restoration and guarded removal also passed
before its qualified binary was reinstalled for manual audition.

## Final pedal state and architecture review

The current WaveFold 0.11 build is installed with all 33 other musical effects.
Its 66 reviewed hardware cases cover the SYMM range, all five stage settings
and all three voices. All 138 measurable native/hardware harmonics passed the
unchanged tolerances after independently verifying the current input routing
and measuring a fresh quiet calibration. The final audit read back all 68
files, checked every saved patch and factory catalogue entry, and confirmed
all diagnostics absent. Both stereo paths passed again after file sessions
closed; autosave is OFF, the current scratch patch is stock-only, and PipeWire
quantum is restored to 128. All 34 icons and the other 33 effect binaries are
byte-identical to the pre-modification backup. Artwork redesign is deferred.

`build/msplus/wavefold-final-20261030-01/COMPLETE.json` binds the exact tested
artifact, accepted analysis, calibration, routing, source fingerprints, final
readback and audio recordings. Native/tool verification passes 28/24 tests.
The architecture check keeps maximum complexity at 136 and reduces duplication
from 10.77% to 10.69%. Remaining flagged complexity is in the required routing,
stage/voice matrix and calibrated harmonic validators; no common DSP ABI or
factory handling was changed.

### Earlier retained-set audit (October 29)

At that checkpoint, the complete set was installed with a stock-only scratch patch selected
and autosave OFF. `build/msplus/retained-34-20261029-01/INSTALLED.json` identifies
all 34 exact binaries; its audit read back all 68 binaries/icons, checked the
factory catalogue, all 100 saved patches and the absence of all four diagnostics.
The full readback `build/msplus/final-factory-readback-20261029-01/` contains 374
CRC-checked files and 100 stock-only saved patches. Compared with the original
306-file backup, all 305 original files except the effect list are byte-identical,
including 149 ZD2, 151 ZIC and two ZIR files. The effect list contains the original
factory entries plus exactly the 34 expected custom entries. Every custom binary
and icon also matches its current build byte-for-byte.

`build/msplus/final-audit-34-20261029-01/FACTORY_MATCH.json` records the content
comparison; `COMPLETE.json` binds the accepted report, full backup and final audio
recording by SHA-256. Both final stereo paths passed after all file sessions had
closed. All 100 saved patches remained unchanged, autosave OFF was acknowledged
again, and PipeWire's original forced quantum of 128 was restored. There are
580,780 bytes free. The pedal is ready for unplugged standalone manual audition.
Do not save a patch containing an experimental effect. Start with one custom
effect at a time; multi-instance memory ownership and aggregate CPU use remain
unqualified. Cross-effect FOLLOW/Mozaic sync and original custom value
labels remain unported. Scrub/GridDly use the documented 15-bit histories.

`verify.py --installed <port names...>` can audit an exact retained set after
qualification: it validates the catalogue with upstream's grammar, requires every
factory entry unchanged plus exactly the named custom entries (including version,
ID and installed flag), and reads every expected custom binary/icon back for
byte equality. Diagnostics must be absent. It also rechecks all saved patches.
This is read-only verification. `install_set.py` separately provides the guarded
retained-set installation described above; it refuses incomplete or stale evidence.

Architecture comparison against `pre-msplus` reduced duplication from 12.24% to
10.92%, average complexity 4.66→4.83, maximum 122→136, and no additional dependency
cycles (six before and after). The analyzer classifies the maximum/clone-count
increases as a regression. The maximum increase is the existing Oxide kernel with both mutually
exclusive ABIs and necessary coefficient/arena/output guards; these checks remain.
The shared Matujuice kernel and control helpers avoid duplicating DSP entry logic;
the remaining adapter similarities are fixed parameter translations and original
control glue. The analysis orchestrator now dispatches specific checks through a
registry. The report generator reuses the retained-install gates, and restoration
proof verification and output-linearity measurement each have one shared
implementation. New tooling reuses upstream packaging, validation and transfers rather
than implementing another protocol. The remaining metric increases reflect the
explicit safety branches, ABI coexistence and added validation, not an altered
musical algorithm or deletion of necessary guards.
