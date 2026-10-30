# Original cover artwork for MS Plus

These 34 monochrome 128×36 panels preserve the authored title and illustration
from each original effect's 128×64 cover. They exclude the old control row at
y=37 and below: Plus firmware draws the live parameters separately.
`sources.json` records the original ZDL, its SHA-256, picture symbol, crop and
extracted PNG hash. Only artwork is extracted; no legacy DSP or Zoom runtime is
included. Matujuice's twelve designs retain their MIT attribution in
[MATUJUICE-LICENSE](../MATUJUICE-LICENSE); the other designs belong to this
repository's original effect pack.

`tools/msplus/artwork.py` places each panel inside a portrait pedal frame, using
nearest-neighbor pixels and the original LCD's approximately 3:2 pixel aspect.
It creates both supported icon sizes, 72×97 and 102×128, with Stomphacks' ZIC
builder and zoom-zt2's stripe encoder. The first frame also replaces the ZD2's
embedded ICON payload. This ports static artwork; it does not transplant the
old firmware's knob positions or UI renderer.

The normal Plus build applies these automatically. To update only artwork in
existing locally validated builds, without recompiling DSP:

```sh
build/msplus/venv/bin/python tools/msplus/artwork.py
# Or: ... tools/msplus/artwork.py flower wavefold
```

This command is offline. Before writing output, it verifies both container
envelopes, byte-exact parse/build round trips, fixed icon geometry and the
complete output against the input with only ICON and CRC permitted to differ.
Hardware qualification retains the original `BUILT.ZD2` and its tested hash;
the retention gate independently repeats that comparison and verifies both
icons against these source pixels. A changed DSP byte, parameter, identity,
section length, header or trailer is rejected, even with a valid new checksum.

Use the documented guarded installer for pedal updates: verify backup and
stock scratch/audio first, dry-run every pair, uninstall the previous custom
pair before installing its replacement, and read back both files. Installing
over an existing filename skips the binary upload in the upstream installer.
