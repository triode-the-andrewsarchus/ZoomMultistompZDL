# MS-70CDR+ development

Experimental ports on branch `feat/ms70cdr-plus`, tested on an actual MS-70CDR+
firmware **1.10**. All **22 original musical effects** and **12 Matujuice v1.5
effects** now build as ZD2. Hardware testing resumed after a physical
restart, then stopped on a newly caught SyncEQ stock-restoration failure. The
latest audit has one valid SyncEQ binary/icon installed, with only stock saved
patches. See the October 29 update below.
Released `dist/*.ZDL` files and the browser editor still target the original
pedals. No Plus release binaries have been published.

## Port inventory and validation

The original 22 are Flower, Klang, Scorch, Corrupt, Howl, Dustbox, GenLoss,
Microlm, Shatter, Arrakis, Taffy, Dissolve, Mangle, Rooms, Hydra, Spiral,
Stasis, Rewire, Gyre, Galactic, Spool and Oxide. All have run
individually on this pedal with finite, unclipped, xrun-free recordings at selected
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
adapters and its license. Two eight-sample calls per Plus callback preserve
source clock cadence. Active output is mono from physical left input, copied
to both outputs, matching the original mono DSP path. Ordinary bypass retains
stereo. DubSiren and GridDly retain their own bypass/tail logic.

The legacy dry-buffer tempo-tag transport has **no verified Plus mapping**.
Adapters use its supported no-tag path. Local tempo and twin-tempo changes are
retained; cross-effect FOLLOW/Mozaic tempo relay is not implemented. Numeric
parameter controls and placeholder name icons are provided; original artwork
and custom value labels are deferred.

Native checks cover all 34 kernels, invalid coefficients, initialization and
arena canaries, selected control extremes, original-versus-Plus sample math,
and independent references for several simpler effects. Hardware checks also
include Klang sidebands, Corrupt sub/master/harmony, Stasis capture/hold while
bypassed/release, and selected Matujuice signatures. Scorch's detailed calibrated
harmonic comparison still fails; it produces stable distortion, but numerical
hardware/reference equivalence is unresolved. Preserve that failure rather than
relaxing its comparison thresholds.

These checks qualify selected standalone cases, not all knob transitions,
long-duration endurance, every source feature or multi-effect chains.

The [current evidence report](MSPLUS-HIL-34.json) records the latest per-port
status as of October 29. Previous snapshots remain in Git history.
**26 effects** pass selected standalone hardware checks. SyncEQ's steady-state
checks also pass, but its return to stock fails and is not qualified. Scorch's
numerical mismatch and DubSiren's transition failure remain unresolved. Five
Matujuice effects still await hardware tests. Retention now additionally requires
an actual verified stock-audio return for each port; only four campaigns currently
have that evidence under the latest guard. Do not retain the full set yet.

## October 29 continuation

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

The fresh storage audit is `build/msplus/audit-synceq-bypassed-transition-01/VERIFIED.json`:
autosave OFF, all 100 saved patches unchanged, all factory catalogue entries intact,
and exactly one valid custom binary/icon, SyncEQ, byte-identical to its build.
The current patch metadata is stock-only. File sessions closed cleanly. A further
physical restart is required to resume audio testing; no firmware,
bootloader or undocumented recovery commands were attempted.

`install_set.py` prepares the requested final manual-audition set, but refuses
before any pedal operations until every musical port has passing required audio
checks, a valid stock baseline, verified stock-audio restoration, and current
binary/source hashes matching its exact hardware evidence. Restoration markers
link to the actual gain/correlation report and recording by SHA-256; a marker
without intact, passing audio evidence is insufficient. It reuses upstream
classification/install/readback, validates all artifacts before the first write,
then audits the entire retained set and stock audio. Sixteen offline
measurement/safety tests cover these gates and stopping on uncertain transfers.
The tool is implemented; it has **not** installed the final set.

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

The 34 ZD2/ZIC pairs total approximately **499 KB** against **1.21 MB free** in
the verified baseline. File sizes suggest enough space to keep all 34 alongside all
factory effects; actual allocated usage must be verified after installation. This is separate from simultaneous processing: the pedal has
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

Within the DSP, bus B reaches input 3 and bus A reaches input 4. Klang's
independent detune and the diagnostic's distinct tones establish this reversal.
The external paths remain output7→input3 and output8→input4.

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

## Scorch reference limitation

The diagnostic emits known triangles (997/1499 Hz, DSP peak at most 0.001),
using only verified small state. `reference.py` estimates DSP-bus-to-return
scaling, then compares Scorch's hardware harmonics against the actual C kernel
compiled natively. It uses the stock-bypass tone to infer input amplitude.

```sh
$PY tools/msplus/reference.py build/msplus/calibrate-hil-0db
$PY tools/msplus/analyze.py build/msplus/campaign-0db-01/scorch/hil \
  --effect scorch --calibration build/msplus/calibrate-hil-0db/calibration.json
# The same --calibration option can be supplied to run.py.
```

The current comparison fails: fundamental output is about 1.5 dB below the
model, third harmonic about 2.7 dB below, and fourth harmonic about 3.5 dB below.
Both return channels show the same pattern. The original single-harmonic fit
reported a 6.4 dB fourth-harmonic error. Jointly fitting ten sine/cosine pairs
plus DC removes leakage between the strong fundamental and weak harmonics in
noninteger-period windows. A synthetic test verifies weak-harmonic extraction
at multiple arbitrary phases. The 1 dB fundamental / 3 dB harmonic limits and
noise threshold remain unchanged; correcting the estimator does not pass Scorch. The exact installed binary/source hashes are preserved. Native
Scorch agrees with an independent scipy filter model; hardware dry-path gain
and capture integrity pass. A simple input/output scale fit did not explain
all harmonics. Calibration/model assumptions, target floating-point behavior
and firmware staging remain possible causes, not established diagnoses.
No acceptance thresholds or effect math were changed to conceal this failure.
Do not consider Scorch quantitatively qualified until this is resolved.


A new `linearity` diagnostic is built and validated **offline only** to investigate
whether the output stage compresses louder signals. It shares the quiet triangle
source, defaults to Level=0, and uses reviewed levels 1/2/5/10/25/50/75/100 followed
by 0. The DSP peak is bounded to 0.55 (first step 0.0055); no external input or
large-memory descriptor is used. Tests verify default silence, the level ceiling,
known RMS, invalid-coefficient rejection, and detection of a saturating output
stage. Its ID is `07001290`, file `XXZLINE.ZD2`; it is **not** one of the 34 musical
ports and has never been uploaded. Refactoring the triangle source preserved the
quiet calibrator's 640-byte `.audio` machine code exactly.

After stock audio is restored, the existing guarded runner can measure this
probe and remove it, with the same backup, autosave, readback and audio-restoration
gates. Comparison reports each channel's gain change from the quiet first step;
changes over 0.5 dB fail the diagnostic rather than being normalized away. A missing
or implausibly scaled quiet reference also fails. This measures a suspected cause,
not an established explanation of the Scorch mismatch.

```sh
# Only after the physical restart and a healthy stock stereo loopback.
$PY tools/msplus/run.py --backup build/msplus/backup-20261028 \
  --output build/msplus/linearity-hil-01 linearity
```

## Final pedal state and architecture review

The last empty-custom storage audit is
`build/msplus/audit-after-power-cycle-01/VERIFIED.json`: autosave OFF, stock scratch,
100 saved patches unchanged, factory effect list byte-identical and all 38
experimental/diagnostic ZD2/ZIC pairs absent. Further documented stock selections
also preserved all saved patches (`build/msplus/stock-reload-02/VERIFIED`).
Factory files were never overwritten or deleted. The verified baseline backup is
`build/msplus/backup-20261028` (306 files, including 300 ZD2/ZIC envelopes).

`verify.py --installed <port names...>` can audit an exact retained set after
qualification: it validates the catalogue with upstream's grammar, requires every
factory entry unchanged plus exactly the named custom entries (including version,
ID and installed flag), and reads every expected custom binary/icon back for
byte equality. Diagnostics must be absent. It also rechecks all saved patches.
This is read-only verification. `install_set.py` separately provides the guarded
retained-set installation described above; it refuses incomplete or stale evidence.

Architecture comparison against `pre-msplus` reduced duplication from 12.24% to
11.05%, average complexity 4.66→4.80, maximum 122→136, and no additional dependency
cycles. The maximum increase is the existing Oxide kernel with both mutually
exclusive ABIs and necessary coefficient/arena/output guards; these checks remain.
The shared Matujuice kernel and control helpers avoid duplicating DSP entry logic;
the remaining adapter similarities are fixed parameter translations and original
control glue. The analysis orchestrator now dispatches specific checks through a
registry. New tooling reuses upstream packaging, validation and transfers rather
than implementing another protocol. The remaining metric increases reflect the
explicit safety branches, ABI coexistence and added validation, not an altered
musical algorithm or deletion of necessary guards.
