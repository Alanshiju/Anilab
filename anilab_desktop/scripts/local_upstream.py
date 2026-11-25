#!/usr/bin/env python3
"""Lightweight local FastAPI upstream for `scripts/resolver.py`.

Serves `/health`, `/search`, `/episodes`, and `/watch` backed by
`~/.anilab_desktop/streams.json` so `anilab_desktop` has a working local
REST upstream out of the box when no external `ANILAB_UPSTREAM_URL` is running.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from anilab_desktop.playback.providers import JsonStreamProvider
from anilab_desktop.state.store import LocalStore

app = FastAPI(title="AniLab Local Upstream", version="0.1.0")


def _provider() -> JsonStreamProvider:
    store = LocalStore()
    prov = JsonStreamProvider(store.get_streams_path())
    prov.ensure_template()
    return prov


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search(q: str = Query("")) -> dict[str, Any]:
    prov = _provider()
    sid = prov.search_match(q)
    if not sid:
        return {"results": []}
    return {"results": [{"id": sid, "title": q}]}


@app.get("/episodes")
def episodes(id: str = Query(...)) -> dict[str, Any]:
    prov = _provider()
    eps = prov.list_episodes(id)
    return {
        "episodes": [
            {
                "id": e.id,
                "number": e.number,
                "title": e.title,
                "is_filler": e.is_filler,
            }
            for e in eps
        ]
    }


@app.get("/watch")
def watch(
    episodeId: str = Query(...),
    id: str | None = Query(None),
) -> dict[str, Any]:
    prov = _provider()
    if not id:
        return {"sources": [], "headers": {}, "subtitles": []}
    res = prov.resolve_stream(id, episodeId)
    if res is None:
        return {"sources": [], "headers": {}, "subtitles": []}
    return {
        "headers": res.headers,
        "sources": [
            {
                "url": res.url,
                "quality": res.quality or "auto",
                "isM3U8": ".m3u8" in res.url.lower(),
            }
        ],
        "subtitles": [
            {"url": s.url, "lang": s.lang, "label": s.label}
            for s in res.subtitles
        ],
    }
