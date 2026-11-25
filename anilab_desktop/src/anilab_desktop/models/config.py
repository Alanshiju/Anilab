"""Configuration and external player models (uj.java, mf.java, jo2.java)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _BaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class PlayerInstallPrompt(_BaseModel):
    title: str | None = None
    description: str | None = None
    downloadsDescription: str | None = None
    buttonLabel: str | None = None
    dismissLabel: str | None = None
    unavailableMessage: str | None = None


class AnimePlayerConfig(_BaseModel):
    appName: str | None = None
    androidPackageId: str | None = None
    androidActivity: str | None = None
    downloadsActivity: str | None = None
    launchExtras: dict[str, str] = Field(default_factory=dict)
    playStoreUrl: str | None = None
    iconUrl: str | None = None
    installPrompt: PlayerInstallPrompt | None = None


class AppConfigResponse(_BaseModel):
    refreshAfterSeconds: int | None = None
    messages: list[dict[str, Any]] = Field(default_factory=list)
    player: AnimePlayerConfig | None = None
    update: dict[str, Any] | None = None
    access: dict[str, Any] | None = Field(default=None, alias="q0")
    feedback: dict[str, Any] | None = None
