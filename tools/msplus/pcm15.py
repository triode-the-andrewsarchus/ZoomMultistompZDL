"""Derive only the PCM read/write adaptation from pinned, pristine Matujuice C.

Keep the upstream dependency untouched. Refuse unexpected source layouts;
build.py verifies the dependency revision and source tree before this runs.
"""
from pathlib import Path


def derive(source: Path, output: Path):
    text = source.read_text()
    substitutions = {
        '#include "../common/drytag.h"': '#include "../matujuice/src/custom/common/drytag.h"',
        '(float)b[j]': '(float)mp_pcm15_read(b, j)',
        '(float)b[j1]': '(float)mp_pcm15_read(b, j1)',
        's->buf[s->wp] = (short)(int)v;': 'mp_pcm15_write(s->buf, s->wp, (int)v);',
    }
    for original, replacement in substitutions.items():
        if text.count(original) != 1:
            raise RuntimeError(f'Unexpected pinned PCM source layout: {source.name}: {original}')
        text = text.replace(original, replacement)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('/* Generated from pinned Matujuice v1.5; see tools/msplus/pcm15.py. */\n' + text)
