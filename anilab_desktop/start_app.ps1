$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# 1. Auto-configure VLC path, Auto fallback mode, and resolver_command in state.json
python -c @"
import json, shutil, sys
from pathlib import Path

root = Path(r'$Root')
state_path = Path.home() / '.anilab_desktop' / 'state.json'
state_path.parent.mkdir(parents=True, exist_ok=True)
data = {}
if state_path.exists():
    try:
        data = json.loads(state_path.read_text(encoding='utf-8'))
    except Exception:
        data = {}

if not data.get('vlc_path'):
    for cand in [
        r'C:\Program Files\VideoLAN\VLC\vlc.exe',
        r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
        shutil.which('vlc.exe') or '',
        shutil.which('vlc') or '',
    ]:
        if cand and Path(cand).is_file():
            data['vlc_path'] = cand
            print(f'[start_app] Configured vlc_path: {cand}')
            break

if not data.get('resolver_command'):
    data['resolver_command'] = [sys.executable, str(root / 'scripts' / 'resolver.py')]
    print('[start_app] Configured resolver_command: scripts/resolver.py')

if data.get('active_provider') not in {'auto', 'json', 'http', 'command'}:
    data['active_provider'] = 'auto'

state_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
"@

# 2. Launch AniLab Desktop directly
$env:PYTHONPATH = "$Root\src"
python -m anilab_desktop
