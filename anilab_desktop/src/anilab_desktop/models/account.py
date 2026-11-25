"""Account, session, and continue-watching models (i8.java, u21.java, hq3.java)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .catalog import AnimeSummary


class _BaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AccountUser(_BaseModel):
    id: int = 0
    name: str = ""
    email: str = ""
    avatarUrl: str | None = None
    joinedAt: int | str | None = None
    showAdultAnimes: bool = False
    access: dict[str, Any] | None = Field(default=None, alias="q0")
    playerToken: str | None = None
    showAvatarInComments: bool = True


class SessionData(_BaseModel):
    token: str | None = None
    user: AccountUser | None = None


class ContinueWatchingItem(_BaseModel):
    anime: AnimeSummary
    watchedAtMs: int = 0
    launchExtras: dict[str, str] | None = None
