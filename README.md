# AniLab Desktop

A lightweight **PySide6 / Qt 6** desktop media catalog and pluggable **VLC** playback shell with watch-progress tracking, in-app web/trailer viewing (`QWebEngineView`), and custom HTTP header (`Referer`, `User-Agent`) & subtitle forwarding.

---

## Tech Stack & Credits
* **Python 3.11+**
* **PySide6 (Qt for Python)** — animated glass-style card UI, `SmoothScrollArea`, and `QWebEngineView`
* **HTTPX & Pydantic v2** — typed REST client & transport layer
* **Cryptography** — AES-256-GCM + HMAC-SHA256 transport framing
* **FastAPI & Uvicorn** — optional local upstream server (`scripts/local_upstream.py`)
* **VLC Media Player (VideoLAN)** — external desktop media playback
* **pytest** — unit test suite

---

## Architecture Overview

```text
anilab_desktop/
├── launch_anilab.bat           # Windows one-click launcher
├── start_app.ps1               # Auto-configures VLC/resolver, starts local upstream, launches UI
├── pyproject.toml
├── scripts/
│   ├── local_upstream.py       # Local FastAPI server backed by ~/.anilab_desktop/streams.json
│   ├── resolver.py             # Subprocess resolver client reading ANILAB_UPSTREAM_URL
│   └── verify_api.py           # Read-only catalog API smoke check
├── src/anilab_desktop/
│   ├── api/                    # HTTPX transport, optional AES-GCM framing, typed client
│   ├── models/                 # Pydantic v2 catalog, config, and account models
│   ├── playback/
│   │   ├── launcher.py         # VLC discovery, header/subtitle CLI forwarding, browser fallback
│   │   └── providers.py        # StreamProvider protocol + implementations
│   ├── state/                  # LocalStore (~/.anilab_desktop/state.json)
│   └── ui/                     # PySide6 views, animated AnimeCard grid, AddStreamDialog, PlayerView
└── tests/                      # Unit tests (crypto, models, playback, providers)
```

### Pluggable `StreamProvider` System
`src/anilab_desktop/playback/providers.py` defines the `StreamProvider` protocol (`search_match`, `list_episodes`, `resolve_stream`):
* **`JsonStreamProvider`**: Reads/writes local user-supplied stream entries in `~/.anilab_desktop/streams.json` (also editable via the in-app **Add / Update Stream** dialog).
* **`HttpJsonStreamProvider`**: Queries a user-configured REST endpoint (`live_provider.base_url` in `~/.anilab_desktop/state.json`).
* **`ResolverCommandProvider`**: Invokes a local script/executable (`scripts/resolver.py` by default) reading `ANILAB_UPSTREAM_URL` (default `http://127.0.0.1:8000`).
* **`FallbackStreamProvider`**: Chains configured providers in order (`Auto (Fallback)` mode).

---

## Setup & Usage

1. **Install dependencies:**
   ```powershell
   cd anilab_desktop
   pip install -e ".[dev]"
   ```

2. **Optional environment variables:**
   * `ANILAB_API_BASE_URL` — catalog REST API base URL (optional)
   * `ANILAB_WIRE_SECRET` — optional transport wire secret (only if your configured catalog API uses AES-GCM framing)
   * `ANILAB_UPSTREAM_URL` — stream resolver upstream URL (defaults to `http://127.0.0.1:8000`)

3. **Run the desktop app:**
   * Double-click `anilab_desktop\launch_anilab.bat` (or run `.\anilab_desktop\start_app.ps1`), or launch directly:
     ```powershell
     cd anilab_desktop
     $env:PYTHONPATH = "src"
     python -m anilab_desktop
     ```

4. **Run tests:**
   ```powershell
   cd anilab_desktop
   pytest -v
   ```

---

## Disclaimer
This software does **not** host, bundle, scrape, or provide any media streams or copyrighted content. It is a desktop catalog and playback shell intended strictly for user-supplied, authorized media sources and local files.
