"""Typed API client wrapping httpx.Client + AniMeloTransport."""

from __future__ import annotations

from typing import Any

import httpx

from anilab_desktop.models.catalog import (
    AnimeDetails,
    AnimeListResponse,
    AnimeProvidersResponse,
    HomeResponse,
)
from anilab_desktop.models.config import AppConfigResponse
from anilab_desktop.state.store import LocalStore

from .transport import AniMeloTransport, BASE_URL


class AniMeloClient:
    """High-level synchronous client for a configured catalog REST API."""

    def __init__(
        self,
        *,
        store: LocalStore | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._store = store
        token_provider = store.get_token if store is not None else None
        self._transport = transport or AniMeloTransport(
            token_provider=token_provider
        )
        resolved_base = (base_url if base_url is not None else BASE_URL).strip()
        self._base_configured = bool(resolved_base)
        self._client = httpx.Client(
            transport=self._transport,
            base_url=resolved_base or "http://127.0.0.1:8000/",
            timeout=httpx.Timeout(timeout, connect=10.0),
        )

    def _ensure_configured(self) -> None:
        if not self._base_configured and isinstance(self._transport, AniMeloTransport):
            # Allow mocked transports in tests; require ANILAB_API_BASE_URL for live calls.
            if type(self._transport._inner).__name__ == "HTTPTransport":
                raise RuntimeError(
                    "ANILAB_API_BASE_URL is not configured. "
                    "Set ANILAB_API_BASE_URL before calling live catalog endpoints."
                )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> AniMeloClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_config(self) -> AppConfigResponse:
        resp = self._client.get("config")
        resp.raise_for_status()
        cfg = AppConfigResponse.model_validate(resp.json())
        if self._store is not None and cfg.player is not None:
            self._store.set_player_config(cfg.player)
        return cfg

    def get_home(self) -> HomeResponse:
        self._ensure_configured()
        resp = self._client.get("home")
        resp.raise_for_status()
        return HomeResponse.model_validate(resp.json())

    def get_anime_details(self, anime_id: int) -> AnimeDetails:
        resp = self._client.get(f"anime/{anime_id}")
        resp.raise_for_status()
        return AnimeDetails.model_validate(resp.json())

    def get_anime_providers(self, anime_id: int) -> AnimeProvidersResponse:
        resp = self._client.get(f"anime/{anime_id}/providers")
        resp.raise_for_status()
        return AnimeProvidersResponse.model_validate(resp.json())

    def search(self, query: str, page: int = 1) -> AnimeListResponse:
        resp = self._client.get(
            "search", params={"query": query, "page": page}
        )
        resp.raise_for_status()
        return AnimeListResponse.model_validate(resp.json())

    def browse(
        self, page: int = 1, filters: dict[str, str] | None = None
    ) -> AnimeListResponse:
        params: dict[str, Any] = {"page": page}
        if filters:
            params.update(filters)
        resp = self._client.get("browse", params=params)
        resp.raise_for_status()
        return AnimeListResponse.model_validate(resp.json())

    def get_section(self, section: str, page: int = 1) -> AnimeListResponse:
        resp = self._client.get(f"sections/{section}", params={"page": page})
        resp.raise_for_status()
        return AnimeListResponse.model_validate(resp.json())

    def get_rankings(self) -> dict[str, Any]:
        resp = self._client.get("rankings")
        resp.raise_for_status()
        return resp.json()

    def get_schedule(
        self, date: str, offset: int = 0, timezone: str = "UTC"
    ) -> dict[str, Any]:
        resp = self._client.get(
            "schedule",
            params={"date": date, "offset": offset, "timezone": timezone},
        )
        resp.raise_for_status()
        return resp.json()
