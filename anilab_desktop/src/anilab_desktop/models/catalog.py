"""Catalog, details, search, browse, schedule, and provider models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .config import AnimePlayerConfig


class _BaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AnimeSummary(_BaseModel):
    id: int
    title: str = ""
    romaji_title: str | None = None
    posterUrl: str | None = None
    largePosterUrl: str | None = None
    type: str | None = None
    score: str | None = None
    latestEpisode: str | None = None
    premiered: str | None = None
    duration: str | None = None
    status: str | None = None
    launchExtras: dict[str, str] | None = None


class AnimeProvider(_BaseModel):
    id: str | None = None
    name: str = ""
    url: str = ""


class StreamingProvider(_BaseModel):
    name: str = ""
    url: str = ""
    iconUrl: str | None = None


class AnimeProvidersResponse(_BaseModel):
    title: str | None = None
    providers: list[StreamingProvider] = Field(default_factory=list)


class AnimeDetails(_BaseModel):
    id: int
    title: str = ""
    romaji_title: str | None = None
    titleEnglish: str | None = None
    titleJapanese: str | None = None
    titleSynonyms: list[str] = Field(default_factory=list)
    synopsis: str | None = None
    posterUrl: str | None = None
    resizedPosterUrl: str | None = None
    type: str | None = None
    rating: str | None = None
    status: str | None = None
    score: str | None = None
    premiered: str | None = None
    aired: str | None = None
    broadcast: str | None = None
    duration: str | None = None
    episodeCount: int | None = None
    lastEpisode: str | None = None
    studios: list[str] = Field(default_factory=list)
    demographics: list[str] = Field(default_factory=list)
    providers: list[AnimeProvider] = Field(default_factory=list)
    trailerUrl: str | None = None
    externalLinks: list[dict[str, Any]] = Field(default_factory=list)
    shareText: str | None = None
    useProvidersPage: bool = False
    commentsCount: int | None = None
    player: AnimePlayerConfig | None = None
    seasons: list[dict[str, Any]] = Field(default_factory=list)
    related: list[dict[str, Any]] = Field(default_factory=list)
    similar: list[AnimeSummary] = Field(default_factory=list)
    tags: list[dict[str, Any]] = Field(default_factory=list)


class HomeResponse(_BaseModel):
    spotlight: list[AnimeSummary] = Field(default_factory=list)
    sections: dict[str, list[AnimeSummary]] = Field(default_factory=dict)


class AnimeListResponse(_BaseModel):
    nextPage: int | None = None
    data: list[AnimeSummary] = Field(default_factory=list)


class RankingsResponse(_BaseModel):
    tabs: list[dict[str, Any]] = Field(default_factory=list)
    data: dict[str, list[AnimeSummary]] | list[AnimeSummary] = Field(
        default_factory=list
    )


class ScheduleResponse(_BaseModel):
    date: str | None = None
    items: list[dict[str, Any]] = Field(default_factory=list)
    data: list[dict[str, Any]] = Field(default_factory=list)
