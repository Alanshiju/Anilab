"""Pydantic v2 domain and DTO models for AniMelo."""

from .account import AccountUser, ContinueWatchingItem, SessionData
from .catalog import (
    AnimeDetails,
    AnimeListResponse,
    AnimeProvider,
    AnimeProvidersResponse,
    AnimeSummary,
    HomeResponse,
    RankingsResponse,
    ScheduleResponse,
    StreamingProvider,
)
from .config import AnimePlayerConfig, AppConfigResponse, PlayerInstallPrompt

__all__ = [
    "AccountUser",
    "AnimeDetails",
    "AnimeListResponse",
    "AnimePlayerConfig",
    "AnimeProvider",
    "AnimeProvidersResponse",
    "AnimeSummary",
    "AppConfigResponse",
    "ContinueWatchingItem",
    "HomeResponse",
    "PlayerInstallPrompt",
    "RankingsResponse",
    "ScheduleResponse",
    "SessionData",
    "StreamingProvider",
]
