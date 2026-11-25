"""AniList GraphQL (https://graphql.anilist.co) catalog client."""

from __future__ import annotations

import html
import re
import time
from typing import Any

import httpx

from anilab_desktop.models.catalog import (
    AnimeDetails,
    AnimeListResponse,
    AnimeProvidersResponse,
    AnimeSummary,
    HomeResponse,
)

ANILIST_URL = "https://graphql.anilist.co"
DEFAULT_CACHE_TTL = 600.0  # 10 minutes

_MEDIA_FIELDS = """
id
title { romaji english native }
coverImage { extraLarge large }
format
status
averageScore
episodes
season
seasonYear
duration
description(asHtml: false)
trailer { id site }
studios(isMain: true) { nodes { name } }
"""

_HOME_QUERY = f"""
query {{
  Page(page: 1, perPage: 24) {{
    media(type: ANIME, sort: TRENDING_DESC, isAdult: false) {{
      {_MEDIA_FIELDS}
    }}
  }}
}}
"""

_SEARCH_QUERY = f"""
query ($search: String, $page: Int) {{
  Page(page: $page, perPage: 24) {{
    pageInfo {{ hasNextPage }}
    media(search: $search, type: ANIME, sort: POPULARITY_DESC, isAdult: false) {{
      {_MEDIA_FIELDS}
    }}
  }}
}}
"""

_BROWSE_QUERY = f"""
query ($page: Int) {{
  Page(page: $page, perPage: 24) {{
    pageInfo {{ hasNextPage }}
    media(type: ANIME, sort: POPULARITY_DESC, isAdult: false) {{
      {_MEDIA_FIELDS}
    }}
  }}
}}
"""

_DETAILS_QUERY = f"""
query ($id: Int) {{
  Media(id: $id, type: ANIME) {{
    {_MEDIA_FIELDS}
  }}
}}
"""


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return html.unescape(cleaned).strip()


def _format_trailer(trailer: dict[str, Any] | None) -> str | None:
    if not isinstance(trailer, dict):
        return None
    site = str(trailer.get("site") or "").lower()
    tid = trailer.get("id")
    if site == "youtube" and tid:
        return f"https://www.youtube.com/watch?v={tid}"
    return None


def _format_premiered(season: str | None, year: int | None) -> str | None:
    if season and year:
        return f"{season.capitalize()} {year}"
    if year:
        return str(year)
    return None


def _map_summary(item: dict[str, Any]) -> AnimeSummary:
    title_obj = item.get("title") or {}
    title = (
        title_obj.get("english")
        or title_obj.get("romaji")
        or title_obj.get("native")
        or ""
    )
    cover = item.get("coverImage") or {}
    img = cover.get("extraLarge") or cover.get("large")
    avg = item.get("averageScore")
    score_str = f"{float(avg) / 10.0:.1f}" if isinstance(avg, (int, float)) else None
    eps = item.get("episodes")
    dur = item.get("duration")
    return AnimeSummary(
        id=int(item["id"]),
        title=str(title),
        posterUrl=img,
        largePosterUrl=img,
        type=item.get("format"),
        score=score_str,
        latestEpisode=str(eps) if eps is not None else None,
        premiered=_format_premiered(item.get("season"), item.get("seasonYear")),
        duration=f"{dur} min per ep" if isinstance(dur, int) else None,
        status=item.get("status"),
    )


def _map_details(item: dict[str, Any]) -> AnimeDetails:
    title_obj = item.get("title") or {}
    title = (
        title_obj.get("english")
        or title_obj.get("romaji")
        or title_obj.get("native")
        or ""
    )
    cover = item.get("coverImage") or {}
    img = cover.get("extraLarge") or cover.get("large")
    avg = item.get("averageScore")
    score_str = f"{float(avg) / 10.0:.1f}" if isinstance(avg, (int, float)) else None
    dur = item.get("duration")
    studios = [
        str(n["name"])
        for n in ((item.get("studios") or {}).get("nodes") or [])
        if isinstance(n, dict) and n.get("name")
    ]
    return AnimeDetails(
        id=int(item["id"]),
        title=str(title),
        titleEnglish=title_obj.get("english"),
        titleJapanese=title_obj.get("native"),
        synopsis=_strip_html(item.get("description")),
        posterUrl=img,
        resizedPosterUrl=img,
        type=item.get("format"),
        status=item.get("status"),
        score=score_str,
        premiered=_format_premiered(item.get("season"), item.get("seasonYear")),
        duration=f"{dur} min per ep" if isinstance(dur, int) else None,
        episodeCount=item.get("episodes"),
        studios=studios,
        trailerUrl=_format_trailer(item.get("trailer")),
        useProvidersPage=False,
    )


class AniListCatalogClient:
    """TTL-cached AniList GraphQL catalog client (no API key required)."""

    def __init__(
        self,
        *,
        base_url: str = ANILIST_URL,
        timeout: float = 25.0,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._url = base_url
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=10.0),
            transport=transport,
        )
        self._cache_ttl = cache_ttl
        self._home_cache: tuple[float, HomeResponse] | None = None
        self._details_cache: dict[int, tuple[float, AnimeDetails]] = {}
        self._search_cache: dict[tuple[str, int], tuple[float, AnimeListResponse]] = {}
        self._browse_cache: dict[int, tuple[float, AnimeListResponse]] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AniListCatalogClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _is_fresh(self, ts: float) -> bool:
        return (time.monotonic() - ts) < self._cache_ttl

    def _post_graphql(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        resp = self._client.post(
            self._url,
            json={"query": query, "variables": variables or {}},
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("errors"):
            raise ValueError(f"AniList GraphQL error: {payload['errors']}")
        return payload.get("data") or {}

    def get_home(self) -> HomeResponse:
        if self._home_cache is not None and self._is_fresh(self._home_cache[0]):
            return self._home_cache[1]
        data = self._post_graphql(_HOME_QUERY)
        media = (data.get("Page") or {}).get("media") or []
        items = [_map_summary(m) for m in media if isinstance(m, dict) and m.get("id")]
        home = HomeResponse(
            spotlight=items[:8],
            sections={"trending": items},
        )
        self._home_cache = (time.monotonic(), home)
        return home

    def search(self, query: str, page: int = 1) -> AnimeListResponse:
        key = (query.strip().lower(), page)
        cached = self._search_cache.get(key)
        if cached is not None and self._is_fresh(cached[0]):
            return cached[1]
        data = self._post_graphql(
            _SEARCH_QUERY, {"search": query, "page": page}
        )
        page_obj = data.get("Page") or {}
        media = page_obj.get("media") or []
        items = [_map_summary(m) for m in media if isinstance(m, dict) and m.get("id")]
        has_next = bool((page_obj.get("pageInfo") or {}).get("hasNextPage"))
        res = AnimeListResponse(
            nextPage=page + 1 if has_next else None,
            data=items,
        )
        self._search_cache[key] = (time.monotonic(), res)
        return res

    def browse(self, page: int = 1) -> AnimeListResponse:
        cached = self._browse_cache.get(page)
        if cached is not None and self._is_fresh(cached[0]):
            return cached[1]
        data = self._post_graphql(_BROWSE_QUERY, {"page": page})
        page_obj = data.get("Page") or {}
        media = page_obj.get("media") or []
        items = [_map_summary(m) for m in media if isinstance(m, dict) and m.get("id")]
        has_next = bool((page_obj.get("pageInfo") or {}).get("hasNextPage"))
        res = AnimeListResponse(
            nextPage=page + 1 if has_next else None,
            data=items,
        )
        self._browse_cache[page] = (time.monotonic(), res)
        return res

    def get_anime_details(self, anime_id: int) -> AnimeDetails:
        cached = self._details_cache.get(anime_id)
        if cached is not None and self._is_fresh(cached[0]):
            return cached[1]
        data = self._post_graphql(_DETAILS_QUERY, {"id": anime_id})
        media = data.get("Media")
        if not isinstance(media, dict):
            raise ValueError(f"AniList returned no Media for id={anime_id}")
        details = _map_details(media)
        self._details_cache[anime_id] = (time.monotonic(), details)
        return details

    def get_anime_providers(self, anime_id: int) -> AnimeProvidersResponse:
        return AnimeProvidersResponse(title=None, providers=[])
