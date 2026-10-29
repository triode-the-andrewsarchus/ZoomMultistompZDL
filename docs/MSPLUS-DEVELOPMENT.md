# MS-70CDR+ development

Experimental ports on branch `feat/ms70cdr-plus`, tested on an actual MS-70CDR+
firmware **1.10**. All **22 original musical effects** and **12 Matujuice v1.5
effects** now build as ZD2. Hardware testing is paused pending a physical
pedal restart after the DubSiren repeat campaign lost the stock audio path.
Released `dist/*.ZDL` files and the browser editor still target the original
pedals. No Plus release binaries have been published.

## Port inventory and validation

The original 22 are Flower, Klang, Scorch, Corrupt, Howl, Dustbox, GenLoss,
Microlm, Shatter, Arrakis, Taffy, Dissolve, Mangle, Rooms, Hydra, Spiral,
Stasis, Rewire, Gyre, Galactic, Spool and Oxide. All except Spiral have run
individually on this pedal with finite, unclipped, xrun-free recordings at selected
settings. Spiral is built/native-tested and still requires its first pedal test.
A stricter activity check found that Rewire's default bit crusher silences the
very quiet test input; its test profile now lowers Bits without changing its
musical defaults. Rooms DIGIT/GATE also need threshold-aware reruns: the native
reference confirms that Time=100, Depth=0 and the existing -20 dBFS send ceiling
produce measurable output. Neither source defaults nor safety limits changed.
Those hardware reruns remain pending.

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

The [34-port evidence report](MSPLUS-HIL-34-20261028.json) records each port's
actual status. **22 effects** currently pass selected standalone hardware checks
including the stricter signal-activity audit: 18 original effects plus WaveFold,
DualShft, Choral and EuGate. Rewire/Rooms need the revised profiles; Scorch has
its unresolved numerical mismatch; Spiral and seven Matujuice effects await
hardware tests. DubSiren generated its intended burst on the first run, but its
repeat campaign is not qualified because the stock baseline was already invalid.
Do not install the full 34-effect set for manual audition yet.

## Bench incident and required continuation

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
for passing. Eleven offline safety tests include invalid/noisy baselines,
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
model; fourth-harmonic error is about -6.4 dB. Both return channels show the
same pattern. The exact installed binary/source hashes are preserved. Native
Scorch agrees with an independent scipy filter model; hardware dry-path gain
and capture integrity pass. A simple input/output scale fit did not explain
all harmonics. Calibration/model assumptions, target floating-point behavior
and firmware staging remain possible causes, not established diagnoses.
No acceptance thresholds or effect math were changed to conceal this failure.
Do not consider Scorch quantitatively qualified until this is resolved.

## Final pedal state and architecture review

The latest full storage audit is
`build/msplus/audit-after-dubsiren-02/VERIFIED.json`: autosave OFF, stock scratch,
100 saved patches unchanged, factory effect list byte-identical and all 37
experimental/diagnostic ZD2/ZIC pairs absent. Further documented stock selections
also preserved all saved patches (`build/msplus/stock-reload-02/VERIFIED`).
Factory files were never overwritten or deleted. The verified baseline backup is
`build/msplus/backup-20261028` (306 files, including 300 ZD2/ZIC envelopes).

`verify.py --installed <port names...>` can audit an exact retained set after
qualification: it validates the catalogue with upstream's grammar, requires every
factory entry unchanged plus exactly the named custom entries (including version,
ID and installed flag), and reads every expected custom binary/icon back for
byte equality. Diagnostics must be absent. It also rechecks all saved patches.
This is read-only verification, not a bulk installer or permission to bypass tests.

Architecture comparison against `pre-msplus` reduced duplication from 12.24% to
11.21%, average complexity 4.66→4.80, maximum 122→136, and no additional dependency
cycles. The maximum increase is the existing Oxide kernel with both mutually
exclusive ABIs and necessary coefficient/arena/output guards; these checks remain.
The shared Matujuice kernel and control helpers avoid duplicating DSP entry logic;
the remaining adapter similarities are fixed parameter translations and original
control glue. The analysis orchestrator now dispatches specific checks through a
registry. New tooling reuses upstream packaging, validation and transfers rather
than implementing another protocol. The remaining metric increases reflect the
explicit safety branches, ABI coexistence and added validation, not an altered
musical algorithm or deletion of necessary guards.
