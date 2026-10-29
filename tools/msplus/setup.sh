#!/usr/bin/env bash
# Dependency setup only: never opens MIDI or audio ports.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build/msplus
python3 - <<'PY'
import json, pathlib, subprocess
lock = json.loads(pathlib.Path('tools/msplus/upstream.lock.json').read_text())
for name, url, dest in [
    ('matujuice-v1.5', 'https://github.com/matujuice/zoom-ms-zdl-effects-pack.git', 'build/msplus/matujuice'),
    ('stomphacks', 'https://github.com/thammer/stomphacks.git', 'build/msplus/stomphacks'),
    ('zoom-zt2', 'https://github.com/mungewell/zoom-zt2.git', 'build/msplus/stomphacks/zoom-zt2'),
]:
    if pathlib.Path(dest).exists():
        raise SystemExit(f'{dest} exists; refusing to overwrite a local checkout.')
    subprocess.run(['git', 'clone', url, dest], check=True)
    subprocess.run(['git', '-C', dest, 'checkout', '--detach', lock[name]], check=True)
dest = 'build/msplus/stomphacks/zoom-zt2'
subprocess.run(['git', '-C', dest, 'fetch', 'origin', lock['zoom-zt2-directory-fix']], check=True)
subprocess.run(['git', '-C', dest, 'cherry-pick', '-n', 'FETCH_HEAD'], check=True)
PY
python3 -m venv build/msplus/venv
ln -s ../venv build/msplus/stomphacks/.venv
build/msplus/venv/bin/pip install -r tools/msplus/requirements.txt
