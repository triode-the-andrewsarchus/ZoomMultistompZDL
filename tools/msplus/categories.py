#!/usr/bin/env python3
"""Offline MS-70CDR+ category migration; never recompiles DSP or opens MIDI.

Edit a port manifest's ID group first, then run this on its existing tested
artifact. Only the header group, full ID, group name/padding and CRC may change.
Saved patches refer to the full ID; hardware replacement must remove the OLD
artifact before installing the new one, using the guarded upstream installer.
"""
import argparse
import hashlib
import json
from pathlib import Path

from upstream import ROOT
import zoomzt2
from pedal_diy import is_diy_id
from stock_catalog import STOCK_IDS
from zd2_from_scratch import GROUP_NAMES, crc32_zd2, verify_envelope, verify_zic

PLUS_GROUPS = {1, 2, 6, 7, 8, 9}


def reclassify(original, new_id):
    """Produce the sole allowed category variant of a valid DIY container."""
    verify_envelope(original)
    config = zoomzt2.ZD2.parse(original)
    if zoomzt2.ZD2.build(config) != original:
        raise ValueError('Category migration requires a byte-exact container round trip')
    group = new_id >> 24
    if group not in PLUS_GROUPS or config.group not in PLUS_GROUPS:
        raise ValueError('Unsupported MS-70CDR+ category')
    if (not is_diy_id(config.id) or not is_diy_id(new_id)
            or config.id in STOCK_IDS or new_id in STOCK_IDS):
        raise ValueError('Category migration is restricted to non-stock DIY IDs')
    if (new_id & 0xffffff) != (config.id & 0xffffff):
        raise ValueError('Category migration must preserve the lower 24 ID bits')
    config.group = group
    config.id = new_id
    config.groupname = GROUP_NAMES[group]
    config.grouppad = bytes(10 - len(config.groupname))
    changed = bytearray(zoomzt2.ZD2.build(config))
    changed[8:12] = crc32_zd2(changed).to_bytes(4, 'little')
    result = bytes(changed)
    verify_envelope(result)
    return result


def check_variant(original, modified, old_zic, new_zic, new_id):
    """Fail closed on any change outside the explicit category transformation."""
    verify_envelope(modified)
    verify_zic(old_zic)
    verify_zic(new_zic)
    if old_zic != new_zic:
        raise ValueError('Category migration changed the companion icon')
    if reclassify(original, new_id) != modified:
        raise ValueError('Changes outside category metadata and CRC')
    before = zoomzt2.ZD2.parse(original)
    return dict(old_id=f'{before.id:08x}', new_id=f'{new_id:08x}',
                category=GROUP_NAMES[new_id >> 24],
                original_sha256=hashlib.sha256(original).hexdigest(),
                binary_sha256=hashlib.sha256(modified).hexdigest(),
                dsp_sha256=hashlib.sha256(bytes(before.DATA.data)).hexdigest(),
                icon_sha256=hashlib.sha256(new_zic).hexdigest(),
                dsp_parameters_artwork_unchanged=True)


def apply(folder):
    manifest = json.loads((folder / 'manifest.json').read_text())
    artifact = folder / 'build' / (manifest['filename'] + '.ZD2')
    original = artifact.read_bytes()
    icon = artifact.with_suffix('.ZIC').read_bytes()
    new_id = int(manifest['id'], 16)
    modified = reclassify(original, new_id)
    proof = check_variant(original, modified, icon, icon, new_id)
    artifact.write_bytes(modified)
    (folder / 'build/CATEGORY.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('effects', nargs='+')
    args = parser.parse_args()
    available = {p.parent.name for p in (ROOT / 'src/msplus').glob('*/manifest.json')}
    if set(args.effects) - available:
        parser.error('Unknown effects: ' + ', '.join(sorted(set(args.effects) - available)))
    for name in args.effects:
        proof = apply(ROOT / 'src/msplus' / name)
        print(f"{name}: {proof['old_id']} -> {proof['new_id']} ({proof['category']}); DSP unchanged")


if __name__ == '__main__':
    main()
