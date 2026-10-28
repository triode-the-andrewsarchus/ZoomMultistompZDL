# MS-70CDR+ development

Work in progress on branch `feat/ms70cdr-plus`. Released `dist/*.ZDL` files
remain for the original generation. No Plus binaries belong in `dist/`.

## Upstream tooling

Use [Stomphacks](https://github.com/thammer/stomphacks) for compilation,
cleanroom scaffolding, ZD2/ZIC packaging, validation and guarded installation.
Read its [SAFETY.md](https://github.com/thammer/stomphacks/blob/main/SAFETY.md)
before opening a session. `tools/msplus/upstream.lock.json` pins dependencies,
including zoom-zt2's directory-enumeration fix (PR 112). Setup never opens MIDI:

```sh
tools/msplus/setup.sh
export ZOOM_TI_CGT=/path/to/ti-cgt-c6000
PY=build/msplus/venv/bin/python
SH=build/msplus/stomphacks
$PY "$SH/tools/zd2_make_effect.py" "$SH/effects/gain/manifest.json"
$PY "$SH/tools-pedal/install_selftest.py"
```

TI's Linux 8.3.15 compiler builds the upstream gain with every REPORT check
passing. Stomphacks documents 8.5.0; this compiler difference must remain in
validation records. Obtain TI tools from [TI](https://www.ti.com/tool/C6000-CGT);
do not commit proprietary tools or pedal backups.

## Session and backup

Only one process may use MIDI. Never save an experimental patch. Never modify
factory files, flash firmware, or issue unknown SysEx. Keep autosave off and
require the pedal's ACK before every audition or installation. A transfer
failure requires clean session closure and verification; keep the pedal powered
if safety cannot be verified. Recovery from storage corruption is not proven.

```sh
$PY "$SH/tools-pedal/safe_connect.py" build/msplus/session-YYYYMMDD
$PY tools/msplus/backup.py build/msplus/backup-YYYYMMDD
```

Our backup retains upstream's enumeration completeness gate and uses its
timeout-bounded, CRC-checking `FileSession` downloader. Patch replies also have
strict CRC and length checks. It requires a fresh destination, verifies every
saved patch references only stock IDs, checks the effect list remains unchanged,
and emits `VERIFIED.json` with SHA-256 hashes only on completion. A directory
without that marker is incomplete. All files are private and git-ignored.

## Audio discovery

Use PipeWire's JACK bridge, specifying exact physical ports. The capture
records all AudioFuse inputs by default. The default send peak is -50 dBFS;
there is no automatic connection to speakers or default audio devices.

```sh
pw-jack $PY tools/msplus/audio.py build/msplus/probe-01 \
  --send 'AF16Rig Audio Pro:playback_AUX6' 'AF16Rig Audio Pro:playback_AUX7'
```

Sends are sequential, independent deterministic noise probes. Inspect the
correlation matrix before choosing return ports. `--kind tone` and `--kind
sweep` generate further signals. Each capture saves send/return WAVs, exact
port names, samplerate, xruns, latency/gain estimates and silence/clipping
checks. Tone correlation alone cannot resolve latency because it is periodic;
use broadband probes. An xrun invalidates a run. Gain/latency include the
interface, pedal and host buffering until a bypass reference is subtracted.

Offline checks (no hardware access):

```sh
$PY -c "import sys; sys.path.insert(0,'tools/msplus'); import upstream; import unittest; unittest.main(module='test_tools')"
```

## Findings from 2026-10-28

USB `1686:07a1`, MIDI device ID `6e`, firmware **1.10**. Stomphacks tested
firmware **1.20**, so compatibility here requires independent validation; do
not update firmware as part of this port. Autosave OFF acknowledged by pedal;
current patch CRC verified. Current edit buffer parses through zoom-zt2's PTCF
reader. AudioFuse reports 34 playback/capture channels at 48 kHz. Initial
low-level probes from playback AUX6/AUX7 correlate with capture AUX2/AUX3,
consistent with the user's physical output 7/8 and input 3/4 routing.

The original kernels' ABI is incompatible: 8-frame channel blocks, one context,
magic shuttle and arena descriptor. Plus uses 16-frame channel blocks, separate
instance/context pointers, in-place `ctx[1]`, coefficients at `instance[1]`,
and a small zeroed `instance[2]` state. Reuse sample math, not the old entry
adapter or proprietary handler blobs. Large delays/loopers need a separately
established memory contract; do not infer one from the old pedal's arena.

## First hardware-validated ports

`src/msplus/gain` (`07001100`, `XXZGAIN`) and `src/msplus/flower`
(`07001110`, `XXZFLWR`) build through Stomphacks without stock templates.
These are private playground identities, not release allocations.

Gain passed on firmware 1.10: relative to stock bypass, stereo unity measured
-0.001/-0.002 dB, half -6.021/-6.021 dB, quarter -12.043/-12.043 dB,
and bypass -0.003/-0.002 dB. Zero removed the correlated stimulus down to
noise. Flower passed dry/half/wet sweeps: dry matches bypass; wet produces
independent moving stereo resonances and the expected high-frequency rolloff.
All captures were finite, unclipped and free of xruns. These tests establish
standalone behavior, not multi-effect DSP capacity or every knob transition.

Flower compiles its existing source under a small conditional ABI adapter;
the legacy .audio machine code remains byte-identical (2432 bytes) to before
the change when compiled with the same TI toolchain. Plus Flower's kernel is
1184 bytes, leaf, with no stack or callee-saved register usage. Mutable state
is 64 bytes plus the generated guard. The shared adapter snapshots parameters,
requires initialized state, silences invalid coefficients, sanitizes inputs,
implements firmware bypass mixing, and rejects non-finite/out-of-bounds output.
Do not reuse the legacy context, magic shuttle or delay descriptor on Plus.

```sh
$PY "$SH/tools/zd2_make_effect.py" src/msplus/gain/manifest.json
$PY "$SH/tools/zd2_make_effect.py" src/msplus/flower/manifest.json
$PY tools/msplus/test_dsp.py
$PY "$SH/tools-pedal/pedal_diy.py" install src/msplus/gain/build/XXZGAIN.ZD2 --dry-run
# Run upstream install as a separate, reviewed operation, then:
pw-jack $PY tools/msplus/audition.py src/msplus/gain \
  build/msplus/backup-YYYYMMDD build/msplus/gain-hil
$PY tools/msplus/analyze.py build/msplus/gain-hil --gain-check
# After RESTORED exists, run upstream uninstall as a separate operation.
```

Audition requires an existing **one-slot stock scratch patch**; it will not
clear or save a patch. It verifies backup hashes, all saved patches, autosave
ACK and independent binary readback before selecting the experimental ID with
the documented parameter-edit command. All edits are read back. It restores
the original stock ID/knobs/on-off state and checks saved patches again. An
unexpected MIDI reply stops further edits rather than blindly attempting
cleanup; inspect the private wire log, keep the pedal powered, and diagnose.
An ordinary audio failure restores the stock patch through the same checked
path. Installation/removal always use upstream's guarded installer.

The 848-byte patch dumps include padding beyond the PTCF's declared length.
That padding can vary between reads without a patch write. Saved-patch checks
therefore compare every defined PTCF byte, retaining the raw dumps and hashes
in the backup. Unsolicited current-patch/parameter notifications are consumed
before fresh requests; unrelated or error replies are rejected.

## Expanded small-state ports and capture safeguards

The additional ports are Klang (32 bytes), Scorch (64), Corrupt (48), Howl
(56), and Dustbox (84). They include their existing C sources, retaining the
sample math while swapping the ABI entry, state access, frame geometry and
bypass writes. All six changed legacy kernels compile to byte-identical legacy
`.audio` sections. Plus skips the old Howl/Dustbox parameter-block latch: the
new initialized coefficient contract supplies validated normalized values.
Corrupt's Plus crossing counter saturates after one second to avoid signed
integer overflow during long unattended silence. Dustbox's development Power
default is 25 instead of 50 to leave capture headroom.

Klang and the larger kernels use Stomphacks' documented `kernel_section: text`,
`allow_stack: true`, `opt_for_space: null` route. This permits compiler-generated
register save/restore, while its verifier still prohibits calls and unresolved
runtime helpers. No verifier checks are disabled or patched. Leaf-only gain
and Flower retain the strict no-stack route.

Build all available ports without opening MIDI:

```sh
build/msplus/venv/bin/python tools/msplus/build.py
# Or select names: ... tools/msplus/build.py gain flower klang
```

`ZOOM_TI_CGT` overrides the compiler root. The current local installation is
`build/msplus/ti/ti-cgt-c6000_8.3.15`, excluded from git. The cleanroom builder
and installer are still upstream tools, not local implementations.

Auditions now keep one JACK stream open across every capture, sending zeros
between probes. They temporarily request PipeWire quantum 1024 and restore
the previous forced quantum on exit, preserving an intervening user change.
The original forced quantum was 128. Earlier runs that reported xruns remain
invalid records; graph/setup xruns before capture are distinguished from xruns
during a recording. Every capture records its actual block size. Signal levels
are -30 dBFS except Scorch's maximum-gain tone, which uses -60 dBFS after a
higher-level trial clipped the interface return. Clipped trials triggered stock
restoration and were not accepted as successful tests.

Klang confirmed an important mapping: on this rig internal Plus bus B reaches
capture AUX2 (physical input 3), bus A reaches AUX3 (input 4). End-to-end sends
remain AUX6->AUX2 and AUX7->AUX3. Its predicted sidebands at 594.1976,
1399.8024, 596.6 and 1397.4 Hz measured 594.1772, 1399.7955, 596.6034 and
1397.4152 Hz. Scorch's dry path is intentionally mono (as in its original
source), so a one-channel probe appears at half amplitude in both returns.

`analyze.py --effect klang` checks sideband frequencies. All analyses name the
checks performed; integrity-only success does not imply sample-for-sample DSP
agreement. Silence recordings check for hot output and growth. Tone recordings
report harmonics 2–5 relative to a 997 Hz fundamental; the result includes the
analog path and its noise floor. Native tests independently compare Flower,
Scorch and Howl with sample/filter references and exercise kernel guards,
parameter faults, channel isolation, persistent state, bypass and long silence.
