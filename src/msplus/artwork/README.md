# Artwork for MS Plus

The current icons are independently drawn at both Plus resolutions in `native/`:
72×97 and 102×128. Titles are typeset at each size, with a pedal body, four
controls, footswitch and an effect-specific motif inspired by the original art.
The normal Plus build and artwork-only update use these native frames directly.
See [the complete preview](../../../docs/images/msplus-native-artwork.png).

`native/designs.json` records the design choices, font and all 68 PNG hashes.
`tools/msplus/art_designs.py` regenerates them using Pillow and the recorded
DejaVu font. The committed PNGs are the packaging inputs; regeneration is not
needed to install them. This is authored pixel art, with no factory image data.

The legacy panels below remain as provenance and design references.

These 34 monochrome 128×36 panels preserve the authored title and illustration
from each original effect's 128×64 cover. Most use rows 0–35; Stasis uses
rows 28–63 because its original controls are above the illustration. The
crops exclude every legacy live value box: Plus firmware draws its live
parameters separately.
`sources.json` records the original ZDL, its SHA-256, picture symbol, crop and
extracted PNG hash. Only artwork is extracted; no legacy DSP or Zoom runtime is
included. Matujuice's twelve designs retain their MIT attribution in
[MATUJUICE-LICENSE](../MATUJUICE-LICENSE); the other designs belong to this
repository's original effect pack.

The earlier artwork revision placed each cropped panel inside a portrait pedal
frame. `tools/msplus/artwork.py` now packages the native frames with Stomphacks' ZIC
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

For an already installed complete set, `install_set.py` accepts
`--replace-artwork-from <fresh-full-backup>`. It validates that backup and
checks each replacement differs only in artwork, dry-runs every install and
removal before writes, then replaces each pair through the upstream tools.
Keep `--backup` pointing to the original factory-only backup for the unchanged
factory catalogue and saved-patch audit. A failed transfer stops the campaign.
