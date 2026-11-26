"""JSON-backed local store for session token, playerToken, and player config."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from anilab_desktop.models.account import SessionData
from anilab_desktop.models.config import AnimePlayerConfig


class LiveProviderConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    base_url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    timeout: float = 15.0


def default_store_path() -> Path:
    return Path.home() / ".anilab_desktop" / "state.json"


def default_streams_path() -> Path:
    return Path.home() / ".anilab_desktop" / "streams.json"


class LocalStore:
    """Persists auth/player tokens and cached AnimePlayerConfig."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_store_path()
        self.session: SessionData = SessionData()
        self.player_config: AnimePlayerConfig | None = None
        self.vlc_path: str | None = None
        self.streams_config_path: str | None = None
        self.active_provider: str = "json"
        self.live_provider: LiveProviderConfig = LiveProviderConfig()
        self.resolver_command: list[str] | str | None = None
        self.resolver_timeout: float = 60.0
        self.last_watched_episode: dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(raw.get("session"), dict):
            self.session = SessionData.model_validate(raw["session"])
        if isinstance(raw.get("player_config"), dict):
            self.player_config = AnimePlayerConfig.model_validate(
                raw["player_config"]
            )
        if isinstance(raw.get("vlc_path"), str) and raw["vlc_path"].strip():
            self.vlc_path = raw["vlc_path"].strip()
        if (
            isinstance(raw.get("streams_config_path"), str)
            and raw["streams_config_path"].strip()
        ):
            self.streams_config_path = raw["streams_config_path"].strip()
        if raw.get("active_provider") in {"auto", "json", "http", "command"}:
            self.active_provider = raw["active_provider"]
        if isinstance(raw.get("live_provider"), dict):
            self.live_provider = LiveProviderConfig.model_validate(
                raw["live_provider"]
            )
        rc = raw.get("resolver_command")
        if isinstance(rc, list) and all(isinstance(x, str) for x in rc):
            self.resolver_command = rc
        elif isinstance(rc, str) and rc.strip():
            self.resolver_command = rc.strip()
        if isinstance(raw.get("resolver_timeout"), (int, float)):
            self.resolver_timeout = max(60.0, float(raw["resolver_timeout"]))
        lwe = raw.get("last_watched_episode")
        if isinstance(lwe, dict):
            self.last_watched_episode = {
                str(k): str(v) for k, v in lwe.items() if v is not None
            }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session": self.session.model_dump(mode="json"),
            "player_config": (
                self.player_config.model_dump(mode="json")
                if self.player_config is not None
                else None
            ),
            "vlc_path": self.vlc_path,
            "streams_config_path": self.streams_config_path,
            "active_provider": self.active_provider,
            "live_provider": self.live_provider.model_dump(mode="json"),
            "resolver_command": self.resolver_command,
            "resolver_timeout": self.resolver_timeout,
            "last_watched_episode": self.last_watched_episode,
        }
        self.path.write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    def get_last_watched(
        self, anime_id: int | None = None, title: str | None = None
    ) -> str | None:
        if anime_id is not None and str(anime_id) in self.last_watched_episode:
            return self.last_watched_episode[str(anime_id)]
        if title and title.strip() in self.last_watched_episode:
            return self.last_watched_episode[title.strip()]
        return None

    def set_last_watched(
        self,
        episode_number: str,
        *,
        anime_id: int | None = None,
        title: str | None = None,
    ) -> None:
        if anime_id is not None:
            self.last_watched_episode[str(anime_id)] = episode_number
        if title and title.strip():
            self.last_watched_episode[title.strip()] = episode_number
        self.save()

    def get_streams_path(self) -> Path:
        if self.streams_config_path:
            return Path(self.streams_config_path)
        return default_streams_path()

    def get_token(self) -> str | None:
        return self.session.token

    def get_player_token(self) -> str | None:
        if self.session.user is None:
            return None
        return self.session.user.playerToken

    def set_session(self, session: SessionData) -> None:
        self.session = session
        self.save()

    def set_player_config(self, config: AnimePlayerConfig | None) -> None:
        self.player_config = config
        self.save()
