#!/usr/bin/env python3
"""Upstream REST resolver client for `anilab_desktop` (`ResolverCommandProvider`).

Reads `ANILAB_UPSTREAM_URL` from the environment (default: `http://127.0.0.1:8000`).
Contract:
  - When `--episode` is omitted: prints `{"series_id": "...", "episodes": [...]}`
  - When `--episode` is provided: prints `{"stream": {"url": "...", "headers": {...}, "subtitles": [...], "quality": "..."}}` or `{"stream": null}`
  - Prints ONLY valid JSON to stdout; all diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

import httpx

DEFAULT_UPSTREAM_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=8.0)


def get_upstream_url(override: str | None = None) -> str:
    raw = (override or os.environ.get("ANILAB_UPSTREAM_URL") or DEFAULT_UPSTREAM_URL).strip()
    return raw if raw.endswith("/") else f"{raw}/"


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _log(msg: str) -> None:
    print(f"[resolver] {msg}", file=sys.stderr)


def _get_json(
    client: httpx.Client, path: str, params: dict[str, Any]
) -> tuple[int, Any | None]:
    try:
        resp = client.get(path, params=params)
        if resp.status_code == 404:
            return 404, None
        resp.raise_for_status()
        return resp.status_code, resp.json()
    except httpx.HTTPError as exc:
        _log(f"HTTP error on {path}: {exc}")
        return 0, None
    except ValueError as exc:
        _log(f"Invalid JSON from {path}: {exc}")
        return 0, None


def _pick_closest_series(items: list[dict[str, Any]], title: str) -> str | None:
    target = normalize_title(title)
    if not target:
        return None

    def _candidates(item: dict[str, Any]) -> list[str]:
        vals: list[str] = []
        for k in ("title", "englishTitle", "romajiTitle", "name"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                vals.append(v)
        aliases = item.get("aliases")
        if isinstance(aliases, list):
            vals.extend(str(a) for a in aliases if a)
        return vals

    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if any(normalize_title(c) == target for c in _candidates(item)):
            return str(item["id"])

    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        for c in _candidates(item):
            norm = normalize_title(c)
            if norm and (target in norm or norm in target):
                return str(item["id"])

    for item in items:
        if isinstance(item, dict) and item.get("id"):
            return str(item["id"])
    return None


def _map_episodes(raw_eps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_eps, list):
        return []
    mapped: list[dict[str, Any]] = []
    for ep in raw_eps:
        if not isinstance(ep, dict):
            continue
        ep_id = str(ep.get("id") or ep.get("number") or "")
        if not ep_id:
            continue
        mapped.append(
            {
                "id": ep_id,
                "number": str(ep.get("number") or ep_id),
                "title": ep.get("title"),
                "is_filler": bool(
                    ep.get("is_filler") or ep.get("isFiller") or False
                ),
            }
        )
    return mapped


def search_and_list_episodes(
    title: str,
    series_id: str | None,
    *,
    base_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Search upstream API by title (unless series_id given) and list episodes."""
    upstream = get_upstream_url(base_url)
    with httpx.Client(
        base_url=upstream, timeout=DEFAULT_TIMEOUT, transport=transport
    ) as client:
        resolved_id = series_id
        if not resolved_id:
            _status, data = _get_json(client, "search", {"q": title})
            if isinstance(data, dict):
                items = data.get("results") or data.get("data") or []
            elif isinstance(data, list):
                items = data
            else:
                items = []
            resolved_id = _pick_closest_series(items, title)
            if not resolved_id:
                _log(f"No matching series found for {title!r} at {upstream}")
                return {"series_id": None, "episodes": []}

        status, ep_data = _get_json(client, "episodes", {"id": resolved_id})
        if status == 404:
            _status, ep_data = _get_json(client, "info", {"id": resolved_id})

        if isinstance(ep_data, dict):
            raw_eps = (
                ep_data.get("episodes")
                or ep_data.get("list")
                or ep_data.get("data")
                or []
            )
        elif isinstance(ep_data, list):
            raw_eps = ep_data
        else:
            raw_eps = []

        return {
            "series_id": resolved_id,
            "episodes": _map_episodes(raw_eps),
        }


def _quality_score(source: dict[str, Any]) -> tuple[int, int]:
    url = str(source.get("url") or "").lower()
    is_hls = int(bool(source.get("isM3U8")) or ".m3u8" in url)
    q = str(source.get("quality") or "").lower()
    m = re.search(r"(\d{3,4})", q)
    res = int(m.group(1)) if m else 0
    return (is_hls, res)


def _extract_headers(raw_headers: Any) -> dict[str, str]:
    if not isinstance(raw_headers, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in raw_headers.items():
        if v is None:
            continue
        kl = str(k).lower()
        if kl in {"referer", "referrer"}:
            out["Referer"] = str(v)
        elif kl == "user-agent":
            out["User-Agent"] = str(v)
        else:
            out[str(k)] = str(v)
    return out


def _extract_subtitles(raw_subs: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_subs, list):
        return []
    subs: list[dict[str, Any]] = []
    for s in raw_subs:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        subs.append(
            {
                "url": str(s["url"]),
                "lang": str(s.get("lang") or "und"),
                "label": s.get("label"),
            }
        )
    return subs


def resolve_episode_stream(
    title: str,
    series_id: str | None,
    episode: str,
    *,
    base_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """Query upstream watch/stream endpoint and return the best HLS/direct stream."""
    upstream = get_upstream_url(base_url)
    _log(
        f"Resolving title={title!r} series_id={series_id!r} episode={episode!r} via {upstream}"
    )

    with httpx.Client(
        base_url=upstream, timeout=DEFAULT_TIMEOUT, transport=transport
    ) as client:
        params: dict[str, Any] = {"episodeId": episode}
        if series_id:
            params["id"] = series_id
        status, data = _get_json(client, "watch", params)
        if status == 404:
            fallback_params: dict[str, Any] = {"episode": episode}
            if series_id:
                fallback_params["id"] = series_id
            _status, data = _get_json(client, "stream", fallback_params)

    if not isinstance(data, dict):
        _log(f"Upstream unavailable or invalid response for episode={episode!r}")
        return {"stream": None}

    inner = data.get("stream") if isinstance(data.get("stream"), dict) else data
    sources = data.get("sources") or inner.get("sources")

    chosen_url: str | None = None
    chosen_quality: str | None = inner.get("quality")

    if isinstance(sources, list) and sources:
        valid = [s for s in sources if isinstance(s, dict) and s.get("url")]
        if valid:
            best = max(valid, key=_quality_score)
            chosen_url = str(best["url"])
            chosen_quality = best.get("quality") or chosen_quality
    else:
        raw_url = inner.get("url") or inner.get("link")
        if raw_url:
            chosen_url = str(raw_url)

    if not chosen_url:
        _log(f"No playable stream URL returned for episode={episode!r}")
        return {"stream": None}

    headers = _extract_headers(data.get("headers") or inner.get("headers"))
    subtitles = _extract_subtitles(
        data.get("subtitles") or inner.get("subtitles")
    )

    return {
        "stream": {
            "url": chosen_url,
            "quality": chosen_quality,
            "headers": headers,
            "subtitles": subtitles,
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="AniLab Desktop stream resolver")
    parser.add_argument("--title", required=True, help="Anime title to match")
    parser.add_argument(
        "--series-id", default=None, help="Optional provider series ID"
    )
    parser.add_argument(
        "--episode", default=None, help="Optional episode ID/number"
    )
    args = parser.parse_args()

    try:
        if args.episode:
            payload = resolve_episode_stream(
                args.title, args.series_id, args.episode
            )
        else:
            payload = search_and_list_episodes(args.title, args.series_id)
    except Exception as exc:
        _log(f"Unhandled error: {exc}")
        return 1

    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
