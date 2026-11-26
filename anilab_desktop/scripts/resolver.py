#!/usr/bin/env python3
"""Example local stream resolver stub for `anilab_desktop` (`ResolverCommandProvider`).

To plug in your own authorized stream resolver, replace this script (or point
`resolver_command` in `~/.anilab_desktop/state.json` to your own script/executable)
while preserving the JSON stdout contract:

  - When `--episode` is omitted:
      {"series_id": "...", "episodes": [{"id": "1", "number": "1", "title": "..."}]}
  - When `--episode` is provided:
      {"stream": {"url": "https://...", "headers": {}, "subtitles": [], "quality": "720p"}}
      or {"stream": null, "error": "..."}
  - Print ONLY valid JSON to stdout; write diagnostics to stderr.

By default, this stub looks up entries in `~/.anilab_desktop/streams.json` and
returns `{"stream": null}` when no matching local entry is configured.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _load_local_streams(streams_path: Path | None = None) -> list[dict[str, Any]]:
    path = streams_path or (Path.home() / ".anilab_desktop" / "streams.json")
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    series = raw.get("series") if isinstance(raw, dict) else None
    return series if isinstance(series, list) else []


def _find_series_entry(
    title: str,
    alt_title: str | None = None,
    *,
    streams_path: Path | None = None,
) -> dict[str, Any] | None:
    targets = {
        normalize_title(t)
        for t in (title, alt_title)
        if t and normalize_title(t)
    }
    if not targets:
        return None
    for entry in _load_local_streams(streams_path):
        if not isinstance(entry, dict):
            continue
        names = [entry.get("title"), *(entry.get("aliases") or [])]
        if any(
            isinstance(n, str) and normalize_title(n) in targets
            for n in names
        ):
            return entry
    return None


def search_and_list_episodes(
    title: str,
    series_id: str | None,
    *,
    count: int = 24,
    streams_path: Path | None = None,
) -> dict[str, Any]:
    """Return configured episodes from streams.json, or a default 1..count placeholder list."""
    entry = _find_series_entry(title, streams_path=streams_path)
    if entry and isinstance(entry.get("episodes"), list) and entry["episodes"]:
        resolved_id = str(entry.get("id") or series_id or normalize_title(title).replace(" ", "-"))
        return {"series_id": resolved_id, "episodes": entry["episodes"]}

    resolved_id = series_id or (normalize_title(title).replace(" ", "-") or "series")
    episodes = [
        {
            "id": str(i),
            "number": str(i),
            "title": f"{title} - Episode {i}",
            "is_filler": False,
        }
        for i in range(1, max(1, count) + 1)
    ]
    return {"series_id": resolved_id, "episodes": episodes}


def resolve_episode_stream(
    title: str,
    series_id: str | None,
    episode: str,
    *,
    alt_title: str | None = None,
    quality: str | None = None,
    streams_path: Path | None = None,
) -> dict[str, Any]:
    """Resolve an episode stream from local streams.json, or return null."""
    _ = (series_id, quality)
    entry = _find_series_entry(title, alt_title, streams_path=streams_path)
    if entry:
        for ep in entry.get("episodes") or []:
            if not isinstance(ep, dict):
                continue
            if str(ep.get("id")) == str(episode) or str(ep.get("number")) == str(episode):
                stream = ep.get("stream")
                if isinstance(stream, dict) and stream.get("url"):
                    return {"stream": stream}

    return {
        "stream": None,
        "error": (
            f"No local stream configured for '{title}' Ep {episode}. "
            "Add a stream via 'Add / Update Stream' or plug in a custom resolver."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AniLab Desktop resolver stub")
    parser.add_argument("--title", required=True, help="Anime title to match")
    parser.add_argument("--alt-title", default=None, help="Optional alternate/romaji title")
    parser.add_argument("--series-id", default=None, help="Optional provider series ID")
    parser.add_argument("--episode", default=None, help="Optional episode ID/number")
    parser.add_argument(
        "--count",
        type=int,
        default=int(os.environ.get("ANILAB_EPISODE_COUNT", "24")),
        help="Number of episodes to list when --episode is omitted",
    )
    args = parser.parse_args()

    if args.episode:
        payload = resolve_episode_stream(
            args.title, args.series_id, args.episode, alt_title=args.alt_title
        )
    else:
        payload = search_and_list_episodes(
            args.title, args.series_id, count=args.count
        )

    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
