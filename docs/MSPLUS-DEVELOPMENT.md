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
