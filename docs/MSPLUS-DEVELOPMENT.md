# MS-70CDR+ development

Experimental source ports on branch `feat/ms70cdr-plus`, tested on an actual
MS-70CDR+ firmware **1.10**. Six of the 22 release effects now build and run,
plus a gain proof of concept. Scorch still fails a detailed reference comparison.
Released `dist/*.ZDL` files and the browser editor target the original generation;
no Plus release binaries have been published.

## Port status

| Port | Mutable state | Hardware validation on 2026-10-28 |
|---|---:|---|
| Gain proof of concept | 4 bytes | Unity, half, quarter, zero and firmware bypass; stereo isolation |
| Flower | 64 bytes | Dry/half/wet and extreme-rate sweeps; independent native reference |
| Klang | 32 bytes | Dry/half/wet; predicted ring sidebands within 1 Hz; extreme settings |
| Scorch | 64 bytes | Mono dry path, wet distortion and silence run; calibrated harmonics **fail**, unresolved |
| Corrupt | 48 bytes | Dry/half/wet; sub/master/harmony at 498.5/997/1994 Hz; adjustable tracking gate |
| Howl | 56 bytes | Dry/half/wet and extreme settings; independent native two-pole reference |
| Dustbox | 84 bytes | Distortion, octave, motor and Power=0 captures; native state/guard checks |

Every listed capture at the final 0 dB interface setting is finite, unclipped,
and free of xruns. This is standalone validation at selected settings, not
complete audio equivalence, all knob transitions, long-duration endurance, or
aggregate DSP capacity. See [numeric results](MSPLUS-HIL-20261028.json).
Native reference tests do not replace hardware comparison.

The other 16 release effects are TapeEcho4, ToTape9, Galactic, Shatter,
Arrakis, Microloom, GenLoss, Taffy, Dissolve, Mangle, Rooms, Hydra, Rewire,
Stasis, Spiral and Gyre. Their delay/history buffers exceed Stomphacks' verified
small-state allocation (188 user bytes plus guard). The Plus large-memory
ownership, allocation size and lifetime contract is not established. No
speculative writes to `instance[3]`, legacy arenas or unverified context slots
were attempted. Establish that contract upstream before porting these effects.

## Build with upstream tooling

[Stomphacks](https://github.com/thammer/stomphacks) supplies the compiler driver,
cleanroom scaffold, ZD2/ZIC packaging, validation and guarded installer. Read its
[SAFETY.md](https://github.com/thammer/stomphacks/blob/main/SAFETY.md),
[DSP ABI](https://github.com/thammer/stomphacks/blob/main/docs/zd2-abi.md) and
installation instructions before hardware work. `tools/msplus/upstream.lock.json`
pins Stomphacks and zoom-zt2, including its directory-enumeration fix (PR 112).
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
non-finite/out-of-bounds outputs. No dynamic allocation or unknown memory is
used. All six modified legacy kernels retain byte-identical legacy `.audio`
sections when built with the same TI compiler.

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
Use private playground IDs `07001100` through `07001170` and filenames `XXZ*`
only after upstream collision checks; these are not public ID allocations.

```sh
$PY "$SH/tools-pedal/safe_connect.py" build/msplus/session-YYYYMMDD
$PY tools/msplus/backup.py build/msplus/backup-YYYYMMDD
# Requires a one-slot, stock-only temporary scratch patch and discovered ports.
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
at -20 dBFS. Earlier +12 dB return trials clipped on loud effects and were
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

## Storage, DSP and final pedal state

The pedal reports 6,204,530 total bytes and **1,210,640 free** with its factory
library. Seven experimental effect/icon pairs occupy about 98 KB allocated;
extrapolating similar sizes to 22 suggests roughly 309 KB. Storage therefore
looks sufficient for all 22 ports, but actual larger builds remain unmeasured.
The [Zoom manual](https://zoomcorp.com/manuals/ms-70cdrplus-en/) specifies
at most six simultaneous effect slots, and DSP limits can reduce that further. Installing 22 does not imply running 22 together.

The final audit confirms autosave OFF, a stock-only temporary patch, all 100
saved patches unchanged, the original effect list byte-identical, and all eight
experimental ZD2/ZIC pairs absent. Factory files were never overwritten or
deleted. The verified backup is `build/msplus/backup-20261028`; final audit is
`build/msplus/final-audit-0db`. The original backup validated 306 files, including
300 factory effect/icon envelopes.

Architecture comparison against `pre-msplus` reduced duplication from 12.24%
to about 11.8%, with average complexity 4.66→4.67 and max unchanged. It flags increased C
entry-point complexity from necessary coefficient guards and mutually exclusive
ABI branches, plus existing legacy arena/magic-shuttle clones in touched files.
Those checks were retained. Its name-based call graph can conflate unrelated
`record` methods; the Python imports remain acyclic. New infrastructure reuses
upstream packaging/transfers and the existing C rather than copying algorithms.
