#!/usr/bin/env python3
"""Package native Plus artwork without recompiling any DSP.

Uses Stomphacks' ZIC builder/envelope checks and zoom-zt2's bitmap transport.
Only the fixed-size ICON payload and container CRC may change in a ZD2.
"""
import argparse
import hashlib
import json
import zlib
from pathlib import Path

from PIL import Image
from upstream import ROOT
import zoomzt2
from convert_zic import restripe
from zd2_from_scratch import ICON_FRAMES, build_zic, verify_envelope, verify_zic


def render_frames(cover):
    # Each frame is authored at its own resolution, including all lettering.
    # Legacy cropped panels remain as inspiration/provenance, not UI content.
    frames = []
    for width, height in ICON_FRAMES:
        path = Path(cover).parent / 'native' / f'{Path(cover).stem}-{width}x{height}.png'
        with Image.open(path) as source:
            if source.size != (width, height) or source.mode != '1':
                raise ValueError('Expected a native-size monochrome Plus icon: ' + str(path))
            frames.append(source.copy())
    return frames


def icon_pair(cover):
    frames = render_frames(cover)
    pixels = [restripe(frame).tobytes() for frame in frames]
    zic = build_zic([(w, h, data) for (w, h), data in zip(ICON_FRAMES, pixels)])
    verify_zic(zic)
    return pixels[0], zic


def check_variant(original, modified, zic, cover):
    """Reject changes to anything except ICON pixels and the validated CRC."""
    verify_envelope(original)
    verify_envelope(modified)
    before, after = (zoomzt2.ZD2.parse(data) for data in (original, modified))
    if zoomzt2.ZD2.build(before) != original or zoomzt2.ZD2.build(after) != modified:
        raise ValueError('Artwork requires a byte-exact container round trip')
    expected_icon, expected_zic = icon_pair(cover)
    if bytes(after.ICON.data) != expected_icon or zic != expected_zic:
        raise ValueError('Packaged artwork differs from the source panel')
    after.ICON.data = before.ICON.data
    after.checksum = before.checksum
    if zoomzt2.ZD2.build(after) != original:
        raise ValueError('Artwork update changed bytes outside ICON and checksum')
    return dict(original_sha256=hashlib.sha256(original).hexdigest(),
                artwork_binary_sha256=hashlib.sha256(modified).hexdigest(),
                dsp_sha256=hashlib.sha256(bytes(before.DATA.data)).hexdigest(),
                source_sha256=hashlib.sha256(b''.join(frame.tobytes() for frame in render_frames(cover))).hexdigest(),
                artwork_format='native Plus icons, independently authored sizes',
                icon_sha256=hashlib.sha256(zic).hexdigest(), dsp_byte_identical=True)


def apply(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    cover = ROOT / 'src/msplus/artwork' / (folder.name + '.png')
    artifact = folder / 'build' / (manifest['filename'] + '.ZD2')
    original = artifact.read_bytes()
    verify_envelope(original)
    config = zoomzt2.ZD2.parse(original)
    if zoomzt2.ZD2.build(config) != original:
        raise ValueError('Container does not round trip byte-exactly')
    icon, zic = icon_pair(cover)
    if config.ICON.length != len(icon):
        raise ValueError('Unexpected container ICON size')
    config.ICON.data = icon
    modified = bytearray(zoomzt2.ZD2.build(config))
    modified[8:12] = (zlib.crc32(modified[12:-16]) ^ 0xffffffff).to_bytes(4, 'little')
    proof = check_variant(original, bytes(modified), zic, cover)
    # All validation completes locally before either upload artifact changes.
    artifact.write_bytes(modified)
    artifact.with_suffix('.ZIC').write_bytes(zic)
    for i, frame in enumerate(render_frames(cover)):
        frame.save(folder / 'build' / f'icon_{i}.png')
    (folder / 'build/ARTWORK.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('effects', nargs='*')
    args = parser.parse_args()
    available = {p.stem for p in (ROOT / 'src/msplus/artwork').glob('*.png')}
    if set(args.effects) - available:
        parser.error('Unknown artwork: ' + ', '.join(sorted(set(args.effects)-available)))
    for name in args.effects or sorted(available):
        apply(ROOT / 'src/msplus' / name)
        print(name + ': native Plus art packaged; DSP and all other sections unchanged')


if __name__ == '__main__':
    main()
