# AniLab Desktop

A modern **PySide6 / Qt 6** desktop anime catalog and pluggable **MPV / VLC** playback shell powered by **AniList GraphQL** (`graphql.anilist.co`) with **Jikan API v4** (`api.jikan.moe`) fallback, featuring an Apple-inspired frosted-glass UI, 60fps smooth scrolling, custom multi-size icon, watch-progress tracking, in-app trailer viewing (`QWebEngineView`), and custom HTTP header (`Referer`, `User-Agent`) & subtitle forwarding.

---

## Highlights & Tech Stack
* **Python 3.11+**
* **PySide6 (Qt for Python)** — frosted-glass UI with cached deep-space ambient backdrop, 2-line elided `AnimeCard`s with cached rounded posters, `SmoothScrollArea`, blurred poster-tinted hero banners, Windows DWM styling, and `QWebEngineView`
* **Custom App Icon (`assets/anilab.ico`)** — multi-size Windows icon (`16px`–`256px`) generated via `scripts/generate_icon.py`
* **AniList GraphQL (`https://graphql.anilist.co`) & Jikan API v4 (`https://api.jikan.moe/v4`)** — fast primary catalog with TTL caching and automatic fallback
* **HTTPX & Pydantic v2** — typed catalog, config, and playback models
* **MPV & VLC Media Player** — external desktop playback with caching, HTTP header fields, audio/subtitle track forwarding, and browser fallback
* **PyInstaller (`build_exe.ps1`)** — single-file (`--onefile --windowed --noconsole`) Windows build script
* **pytest** — unit test suite

---

## Architecture Overview

```text
anilab_desktop/
├── assets/
│   └── anilab.ico              # Multi-size glassmorphism Windows icon
├── build_exe.ps1               # Single-EXE PyInstaller build script
├── launch_anilab.bat           # Windows one-click launcher
├── start_app.ps1               # Auto-configures player/resolver and launches UI
├── pyproject.toml
├── scripts/
│   ├── generate_icon.py        # Renders assets/anilab.ico via PySide6 QPainter
│   ├── local_upstream.py       # Optional local FastAPI server backed by streams.json
│   └── resolver.py             # Neutral resolver stub (reads streams.json or custom plugin)
├── src/anilab_desktop/
│   ├── api/                    # AniListCatalogClient + JikanCatalogClient + FallbackCatalogClient
│   ├── models/                 # Pydantic v2 catalog, config, and account models
│   ├── playback/
│   │   ├── launcher.py         # MPV/VLC discovery, header/subtitle CLI forwarding, browser fallback
│   │   └── providers.py        # StreamProvider protocol + JSON, HTTP, Command, Bundled, Fallback providers
│   ├── state/                  # LocalStore (~/.anilab_desktop/state.json)
│   └── ui/                     # Frosted-glass views, AnimeCard grid, EpisodesDialog, AddStreamDialog, PlayerView
└── tests/                      # Unit tests (models, catalog clients, playback, providers)
```

### Pluggable `StreamProvider` System
`src/anilab_desktop/playback/providers.py` defines the `StreamProvider` protocol (`search_match`, `list_episodes`, `resolve_stream`):
* **`JsonStreamProvider`**: Reads/writes local user-supplied stream entries in `~/.anilab_desktop/streams.json` (editable via the in-app **Add / Update Stream** dialog).
* **`HttpJsonStreamProvider`**: Queries a user-configured REST endpoint (`live_provider.base_url` in `~/.anilab_desktop/state.json`).
* **`ResolverCommandProvider` / `BundledResolverProvider`**: Invokes a local user-supplied script/executable (`scripts/resolver.py` by default).
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

4. **Build standalone Windows `.exe` (optional):**
   ```powershell
   cd anilab_desktop
   .\build_exe.ps1
   ```

---

## Disclaimer
This software does **not** host, bundle, scrape, or provide any media streams or copyrighted content. Catalog metadata is fetched from the public **AniList GraphQL API** (`graphql.anilist.co`) and **Jikan API v4** (`api.jikan.moe`), and episode playback is intended strictly for user-supplied, authorized media sources and local files.
