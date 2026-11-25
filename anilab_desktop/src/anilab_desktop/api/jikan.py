"""Jikan API v4 (https://api.jikan.moe/v4) catalog client."""

from __future__ import annotations

import threading
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

JIKAN_BASE_URL = "https://api.jikan.moe/v4/"
DEFAULT_CACHE_TTL = 600.0  # 10 minutes


def _extract_images(item: dict[str, Any]) -> tuple[str | None, str | None]:
    images = item.get("images") or {}
    jpg = images.get("jpg") or images.get("webp") or {}
    small = jpg.get("image_url")
    large = jpg.get("large_image_url") or small
    return small, large


def _map_summary(item: dict[str, Any]) -> AnimeSummary:
    small, large = _extract_images(item)
    score_val = item.get("score")
    score_str = f"{float(score_val):.1f}" if isinstance(score_val, (int, float)) else None
    eps_val = item.get("episodes")
    ep_str = str(eps_val) if eps_val is not None else None
    year = item.get("year")
    season = item.get("season")
    premiered = (
        f"{str(season).capitalize()} {year}"
        if season and year
        else (str(year) if year else None)
    )
    return AnimeSummary(
        id=int(item["mal_id"]),
        title=str(item.get("title_english") or item.get("title") or ""),
        posterUrl=small,
        largePosterUrl=large,
        type=item.get("type"),
        score=score_str,
        latestEpisode=ep_str,
        premiered=premiered,
        duration=item.get("duration"),
        status=item.get("status"),
    )


def _map_details(item: dict[str, Any]) -> AnimeDetails:
    small, large = _extract_images(item)
    score_val = item.get("score")
    score_str = f"{float(score_val):.1f}" if isinstance(score_val, (int, float)) else None
    year = item.get("year")
    season = item.get("season")
    premiered = (
        f"{str(season).capitalize()} {year}"
        if season and year
        else (str(year) if year else None)
    )
    trailer = item.get("trailer") or {}
    trailer_url = trailer.get("embed_url") or trailer.get("url")
    studios = [
        str(s["name"])
        for s in (item.get("studios") or [])
        if isinstance(s, dict) and s.get("name")
    ]
    demographics = [
        str(d["name"])
        for d in (item.get("demographics") or [])
        if isinstance(d, dict) and d.get("name")
    ]
    aired_obj = item.get("aired") or {}
    aired_str = aired_obj.get("string") if isinstance(aired_obj, dict) else None

    return AnimeDetails(
        id=int(item["mal_id"]),
        title=str(item.get("title_english") or item.get("title") or ""),
        titleEnglish=item.get("title_english"),
        titleJapanese=item.get("title_japanese"),
        titleSynonyms=[
            str(s) for s in (item.get("title_synonyms") or []) if s
        ],
        synopsis=item.get("synopsis"),
        posterUrl=small,
        resizedPosterUrl=large,
        type=item.get("type"),
        rating=item.get("rating"),
        status=item.get("status"),
        score=score_str,
        premiered=premiered,
        aired=aired_str,
        duration=item.get("duration"),
        episodeCount=item.get("episodes"),
        studios=studios,
        demographics=demographics,
        trailerUrl=trailer_url,
        useProvidersPage=False,
    )


class JikanCatalogClient:
    """Rate-limited, TTL-cached client for Jikan API v4 (https://api.jikan.moe/v4)."""

    def __init__(
        self,
        *,
        base_url: str = JIKAN_BASE_URL,
        timeout: float = 25.0,
        min_interval: float = 0.35,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        resolved = base_url if base_url.endswith("/") else f"{base_url}/"
        self._client = httpx.Client(
            base_url=resolved,
            timeout=httpx.Timeout(timeout, connect=10.0),
            transport=transport,
        )
        self._min_interval = min_interval
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        self._last_req_at = 0.0
        self._home_cache: tuple[float, HomeResponse] | None = None
        self._details_cache: dict[int, tuple[float, AnimeDetails]] = {}
        self._search_cache: dict[tuple[str, int], tuple[float, AnimeListResponse]] = {}
        self._browse_cache: dict[int, tuple[float, AnimeListResponse]] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JikanCatalogClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _is_fresh(self, ts: float) -> bool:
        return (time.monotonic() - ts) < self._cache_ttl

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_req_at)
            if wait > 0:
                time.sleep(wait)
            resp = self._client.get(path, params=params)
            self._last_req_at = time.monotonic()
            resp.raise_for_status()
            return resp.json()

    def get_home(self) -> HomeResponse:
        if self._home_cache is not None and self._is_fresh(self._home_cache[0]):
            return self._home_cache[1]

        seasonal_raw = self._get_json(
            "seasons/now", {"sfw": "true", "limit": 24}
        )
        airing = [
            _map_summary(x)
            for x in (seasonal_raw.get("data") or [])
            if isinstance(x, dict) and x.get("mal_id")
        ]
        home = HomeResponse(
            spotlight=airing[:8],
            sections={"airing": airing},
        )
        self._home_cache = (time.monotonic(), home)
        return home

    def search(self, query: str, page: int = 1) -> AnimeListResponse:
        key = (query.strip().lower(), page)
        cached = self._search_cache.get(key)
        if cached is not None and self._is_fresh(cached[0]):
            return cached[1]

        raw = self._get_json(
            "anime",
            {"q": query, "sfw": "true", "limit": 24, "page": page},
        )
        items = [
            _map_summary(x)
            for x in (raw.get("data") or [])
            if isinstance(x, dict) and x.get("mal_id")
        ]
        has_next = bool((raw.get("pagination") or {}).get("has_next_page"))
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

        raw = self._get_json(
            "top/anime",
            {"sfw": "true", "limit": 24, "page": page},
        )
        items = [
            _map_summary(x)
            for x in (raw.get("data") or [])
            if isinstance(x, dict) and x.get("mal_id")
        ]
        has_next = bool((raw.get("pagination") or {}).get("has_next_page"))
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

        raw = self._get_json(f"anime/{anime_id}/full")
        data = raw.get("data")
        if not isinstance(data, dict):
            raise ValueError(f"Unexpected Jikan response for anime {anime_id}")
        details = _map_details(data)
        self._details_cache[anime_id] = (time.monotonic(), details)
        return details

    def get_anime_providers(self, anime_id: int) -> AnimeProvidersResponse:
        return AnimeProvidersResponse(title=None, providers=[])
