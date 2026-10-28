"""Locate the pinned Stomphacks checkout; do not duplicate its packager/transport."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STOMPHACKS = Path(os.environ.get('STOMPHACKS_ROOT', ROOT / 'build/msplus/stomphacks')).resolve()
if not (STOMPHACKS / 'tools/zd2_make_effect.py').is_file():
    raise SystemExit('Run tools/msplus/setup.sh, or set STOMPHACKS_ROOT to your checkout.')
for folder in ('zoom-zt2', 'tools', 'tools-pedal'):
    sys.path.insert(0, str(STOMPHACKS / folder))
