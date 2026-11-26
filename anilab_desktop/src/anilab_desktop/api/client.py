"""Catalog client factory with automatic Jikan -> AniList fallback."""

from __future__ import annotations

import os

from anilab_desktop.models.catalog import (
    AnimeDetails,
    AnimeListResponse,
    AnimeProvidersResponse,
    HomeResponse,
)

from .anilist import AniListCatalogClient
from .jikan import JIKAN_BASE_URL, JikanCatalogClient


class FallbackCatalogClient:
    """Tries primary (AniList GraphQL) and falls back to Jikan v4 on error."""

    def __init__(
        self,
        primary: Any = None,
        fallback: Any = None,
    ) -> None:
        self._primary = primary or AniListCatalogClient()
        self._fallback = fallback or JikanCatalogClient()
        self._id_source: dict[int, str] = {}

    def close(self) -> None:
        self._primary.close()
        self._fallback.close()

    def __enter__(self) -> FallbackCatalogClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _record_ids(self, items, source: str) -> None:
        for item in items:
            self._id_source[item.id] = source

    def get_home(self) -> HomeResponse:
        try:
            res = self._primary.get_home()
            self._record_ids(res.spotlight, "primary")
            for lst in res.sections.values():
                self._record_ids(lst, "primary")
            return res
        except Exception:
            res = self._fallback.get_home()
            self._record_ids(res.spotlight, "fallback")
            for lst in res.sections.values():
                self._record_ids(lst, "fallback")
            return res

    def search(self, query: str, page: int = 1) -> AnimeListResponse:
        try:
            res = self._primary.search(query, page=page)
            self._record_ids(res.data, "primary")
            return res
        except Exception:
            res = self._fallback.search(query, page=page)
            self._record_ids(res.data, "fallback")
            return res

    def browse(self, page: int = 1) -> AnimeListResponse:
        try:
            res = self._primary.browse(page=page)
            self._record_ids(res.data, "primary")
            return res
        except Exception:
            res = self._fallback.browse(page=page)
            self._record_ids(res.data, "fallback")
            return res

    def get_anime_details(self, anime_id: int) -> AnimeDetails:
        src = self._id_source.get(anime_id)
        if src == "fallback":
            return self._fallback.get_anime_details(anime_id)
        try:
            return self._primary.get_anime_details(anime_id)
        except Exception:
            return self._fallback.get_anime_details(anime_id)

    def get_anime_providers(self, anime_id: int) -> AnimeProvidersResponse:
        return AnimeProvidersResponse(title=None, providers=[])


def create_catalog_client() -> FallbackCatalogClient:
    """Create a FallbackCatalogClient (AniList GraphQL primary -> Jikan v4 fallback)."""
    override = os.environ.get("ANILAB_API_BASE_URL", "").strip()
    primary = AniListCatalogClient()
    fallback = JikanCatalogClient(base_url=override or JIKAN_BASE_URL)
    return FallbackCatalogClient(primary=primary, fallback=fallback)
