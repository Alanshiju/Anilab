# AniLab Desktop

A lightweight **PySide6 / Qt 6** desktop anime catalog and pluggable **VLC** playback shell powered out of the box by **Jikan API v4** (`api.jikan.moe`), featuring animated glassmorphism cards, watch-progress tracking, in-app trailer/web viewing (`QWebEngineView`), and custom HTTP header (`Referer`, `User-Agent`) & subtitle forwarding.

---

## Tech Stack & Credits
* **Python 3.11+**
* **PySide6 (Qt for Python)** — animated glassmorphism UI, `SmoothScrollArea`, and `QWebEngineView`
* **Jikan API v4 (`https://api.jikan.moe/v4`)** — open MyAnimeList REST API for seasonal/top catalogs, search, posters, metadata, and trailers
* **HTTPX & Pydantic v2** — rate-limited REST client & typed models
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
│   └── resolver.py             # Subprocess resolver client reading ANILAB_UPSTREAM_URL
├── src/anilab_desktop/
│   ├── api/                    # JikanCatalogClient (rate-limited + cached)
│   ├── models/                 # Pydantic v2 catalog, config, and account models
│   ├── playback/
│   │   ├── launcher.py         # VLC discovery, header/subtitle CLI forwarding, browser fallback
│   │   └── providers.py        # StreamProvider protocol + implementations
│   ├── state/                  # LocalStore (~/.anilab_desktop/state.json)
│   └── ui/                     # PySide6 glassmorphism views, AnimeCard grid, AddStreamDialog, PlayerView
└── tests/                      # Unit tests (Jikan client, models, playback, providers)
```

### Pluggable `StreamProvider` System
`src/anilab_desktop/playback/providers.py` defines the `StreamProvider` protocol (`search_match`, `list_episodes`, `resolve_stream`):
* **`JsonStreamProvider`**: Reads/writes local user-supplied stream entries in `~/.anilab_desktop/streams.json` (editable via the in-app **Add / Update Stream** dialog).
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

2. **Run the desktop app:**
   * Double-click `anilab_desktop\launch_anilab.bat` (or run `.\anilab_desktop\start_app.ps1`), or launch directly:
     ```powershell
     cd anilab_desktop
     $env:PYTHONPATH = "src"
     python -m anilab_desktop
     ```

3. **Run tests:**
   ```powershell
   cd anilab_desktop
   pytest -v
   ```

---

## Disclaimer
This software does **not** host, bundle, scrape, or provide any media streams or copyrighted content. Catalog metadata is fetched from the public **Jikan API v4** (`api.jikan.moe`), and episode playback is intended strictly for user-supplied, authorized media sources and local files.
