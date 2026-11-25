$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not $env:ANILAB_UPSTREAM_URL) {
    $env:ANILAB_UPSTREAM_URL = "http://127.0.0.1:8000"
}

# 1. Auto-configure VLC path, Auto fallback mode, and resolver_command in state.json
python -c @"
import json, shutil
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
    import sys
    data['resolver_command'] = [sys.executable, str(root / 'scripts' / 'resolver.py')]
    print('[start_app] Configured resolver_command: scripts/resolver.py')

if data.get('active_provider') not in {'auto', 'json', 'http', 'command'}:
    data['active_provider'] = 'auto'

state_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
"@

# 2. Check if ANILAB_UPSTREAM_URL is reachable; start local_upstream.py if not
$upstreamProc = $null
$isReachable = $false
try {
    $resp = Invoke-WebRequest -Uri ($env:ANILAB_UPSTREAM_URL.TrimEnd('/') + "/health") -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
    if ($resp.StatusCode -eq 200) { $isReachable = $true }
} catch {
    $isReachable = $false
}

if (-not $isReachable) {
    Write-Host "[start_app] Starting local upstream server at $env:ANILAB_UPSTREAM_URL ..."
    $upstreamProc = Start-Process -FilePath "python" -ArgumentList @("-m", "uvicorn", "scripts.local_upstream:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning") -WorkingDirectory $Root -WindowStyle Hidden -PassThru

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 250
        try {
            $resp = Invoke-WebRequest -Uri ($env:ANILAB_UPSTREAM_URL.TrimEnd('/') + "/health") -TimeoutSec 1 -UseBasicParsing -ErrorAction Stop
            if ($resp.StatusCode -eq 200) {
                $isReachable = $true
                break
            }
        } catch {}
    }
    if ($isReachable) {
        Write-Host "[start_app] Local upstream is ready."
    } else {
        Write-Warning "[start_app] Local upstream did not respond in time; continuing anyway."
    }
} else {
    Write-Host "[start_app] Using running upstream at $env:ANILAB_UPSTREAM_URL"
}

# 3. Launch anilab_desktop
try {
    $env:PYTHONPATH = "$Root\src"
    python -m anilab_desktop
} finally {
    if ($upstreamProc -and -not $upstreamProc.HasExited) {
        Stop-Process -Id $upstreamProc.Id -Force -ErrorAction SilentlyContinue
    }
}
