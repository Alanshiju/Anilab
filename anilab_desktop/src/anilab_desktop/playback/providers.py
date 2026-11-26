"""Pluggable StreamProvider protocol and local JsonStreamProvider."""

from __future__ import annotations

import importlib.util
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class SubtitleTrack:
    url: str
    lang: str
    label: str | None = None


@dataclass(frozen=True)
class EpisodeInfo:
    id: str
    number: str
    title: str | None = None
    is_filler: bool = False


@dataclass(frozen=True)
class StreamResult:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    subtitles: list[SubtitleTrack] = field(default_factory=list)
    audio_urls: list[str] = field(default_factory=list)
    quality: str | None = None


class StreamProvider(Protocol):
    name: str

    def search_match(self, title: str) -> str | None:
        """Return a provider-specific series/post ID matching `title`, or None."""
        ...

    def list_episodes(self, series_id: str) -> list[EpisodeInfo]:
        """Return available episodes for `series_id`."""
        ...

    def resolve_stream(
        self, series_id: str, episode_id: str
    ) -> StreamResult | None:
        """Resolve a direct stream URL + headers + subtitles for an episode."""
        ...


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class JsonStreamProvider:
    """Local JSON-backed StreamProvider reading ~/.anilab_desktop/streams.json."""

    name: str = "Local JSON Streams"

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = (
            config_path
            if config_path is not None
            else Path.home() / ".anilab_desktop" / "streams.json"
        )

    @staticmethod
    def template_payload() -> dict[str, Any]:
        return {
            "series": [
                {
                    "id": "example-series",
                    "title": "Example Anime Title",
                    "aliases": [],
                    "episodes": [
                        {
                            "id": "ep-1",
                            "number": "1",
                            "title": "Episode 1",
                            "is_filler": False,
                            "stream": {
                                "url": "https://example.com/stream/master.m3u8",
                                "quality": "1080p",
                                "headers": {},
                                "subtitles": [],
                            },
                        }
                    ],
                }
            ]
        }

    def ensure_template(self) -> Path:
        """Create an empty/template streams.json if it does not exist."""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps({"series": []}, indent=2), encoding="utf-8"
            )
        return self.config_path

    def upsert_episode(
        self,
        anime_title: str,
        episode_number: str,
        stream_url: str,
        *,
        episode_title: str | None = None,
        referer: str | None = None,
        user_agent: str | None = None,
        subtitle_url: str | None = None,
        quality: str | None = None,
    ) -> tuple[str, str]:
        """Add or update a series/episode stream entry in streams.json."""
        title_clean = anime_title.strip()
        ep_num = episode_number.strip()
        url_clean = stream_url.strip()
        if not title_clean or not ep_num or not url_clean:
            raise ValueError(
                "Anime title, episode number, and stream URL are required."
            )

        self.ensure_template()
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        series_list = raw.get("series")
        if not isinstance(series_list, list):
            series_list = []
            raw["series"] = series_list

        matched_id = self.search_match(title_clean)
        target_series: dict[str, Any] | None = None
        if matched_id is not None:
            for entry in series_list:
                if (
                    isinstance(entry, dict)
                    and str(entry.get("id")) == matched_id
                ):
                    target_series = entry
                    break

        if target_series is None:
            slug = _normalize_title(title_clean).replace(" ", "-") or "series"
            existing_ids = {
                str(e.get("id")) for e in series_list if isinstance(e, dict)
            }
            series_id = slug
            suffix = 2
            while series_id in existing_ids:
                series_id = f"{slug}-{suffix}"
                suffix += 1
            target_series = {
                "id": series_id,
                "title": title_clean,
                "aliases": [],
                "episodes": [],
            }
            series_list.append(target_series)
        else:
            series_id = str(target_series["id"])

        episodes = target_series.get("episodes")
        if not isinstance(episodes, list):
            episodes = []
            target_series["episodes"] = episodes

        ep_id = f"ep-{ep_num}"
        headers: dict[str, str] = {}
        if referer and referer.strip():
            headers["Referer"] = referer.strip()
        if user_agent and user_agent.strip():
            headers["User-Agent"] = user_agent.strip()

        subtitles: list[dict[str, str]] = []
        if subtitle_url and subtitle_url.strip():
            subtitles.append(
                {
                    "url": subtitle_url.strip(),
                    "lang": "en",
                    "label": "English",
                }
            )

        stream_obj: dict[str, Any] = {
            "url": url_clean,
            "headers": headers,
            "subtitles": subtitles,
        }
        if quality and quality.strip():
            stream_obj["quality"] = quality.strip()

        ep_obj: dict[str, Any] = {
            "id": ep_id,
            "number": ep_num,
            "title": episode_title.strip() if episode_title and episode_title.strip() else None,
            "is_filler": False,
            "stream": stream_obj,
        }

        replaced = False
        for idx, existing in enumerate(episodes):
            if not isinstance(existing, dict):
                continue
            ex_id = str(existing.get("id") or "")
            ex_num = str(existing.get("number") or "")
            if ex_id == ep_id or ex_num == ep_num:
                ep_obj["id"] = ex_id or ep_id
                ep_id = str(ep_obj["id"])
                episodes[idx] = ep_obj
                replaced = True
                break
        if not replaced:
            episodes.append(ep_obj)

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(raw, indent=2), encoding="utf-8"
        )
        return series_id, ep_id

    def _load_series(self) -> list[dict[str, Any]]:
        if not self.config_path.exists():
            return []
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        series = raw.get("series") if isinstance(raw, dict) else None
        return series if isinstance(series, list) else []

    def search_match(self, title: str) -> str | None:
        target = _normalize_title(title)
        if not target:
            return None
        series_list = self._load_series()

        # Pass 1: exact normalized match on title or aliases
        for entry in series_list:
            if not isinstance(entry, dict):
                continue
            sid = entry.get("id")
            if not sid:
                continue
            candidates = [entry.get("title", "")]
            aliases = entry.get("aliases")
            if isinstance(aliases, list):
                candidates.extend(str(a) for a in aliases)
            if any(_normalize_title(str(c)) == target for c in candidates if c):
                return str(sid)

        # Pass 2: substring normalized match
        for entry in series_list:
            if not isinstance(entry, dict):
                continue
            sid = entry.get("id")
            if not sid:
                continue
            candidates = [entry.get("title", "")]
            aliases = entry.get("aliases")
            if isinstance(aliases, list):
                candidates.extend(str(a) for a in aliases)
            for c in candidates:
                norm = _normalize_title(str(c))
                if norm and (target in norm or norm in target):
                    return str(sid)
        return None

    def list_episodes(self, series_id: str) -> list[EpisodeInfo]:
        for entry in self._load_series():
            if not isinstance(entry, dict) or str(entry.get("id")) != series_id:
                continue
            raw_eps = entry.get("episodes")
            if not isinstance(raw_eps, list):
                return []
            out: list[EpisodeInfo] = []
            for ep in raw_eps:
                if not isinstance(ep, dict):
                    continue
                ep_id = str(ep.get("id") or ep.get("number") or "")
                if not ep_id:
                    continue
                out.append(
                    EpisodeInfo(
                        id=ep_id,
                        number=str(ep.get("number") or ep_id),
                        title=ep.get("title"),
                        is_filler=bool(ep.get("is_filler", False)),
                    )
                )
            return out
        return []

    def resolve_stream(
        self, series_id: str, episode_id: str
    ) -> StreamResult | None:
        for entry in self._load_series():
            if not isinstance(entry, dict) or str(entry.get("id")) != series_id:
                continue
            raw_eps = entry.get("episodes")
            if not isinstance(raw_eps, list):
                return None
            for ep in raw_eps:
                if not isinstance(ep, dict):
                    continue
                ep_id = str(ep.get("id") or ep.get("number") or "")
                if ep_id != episode_id:
                    continue
                stream = ep.get("stream")
                if not isinstance(stream, dict) or not stream.get("url"):
                    return None
                headers = {
                    str(k): str(v)
                    for k, v in (stream.get("headers") or {}).items()
                    if v is not None
                }
                subs: list[SubtitleTrack] = []
                for s in stream.get("subtitles") or []:
                    if isinstance(s, dict) and s.get("url"):
                        subs.append(
                            SubtitleTrack(
                                url=str(s["url"]),
                                lang=str(s.get("lang") or "und"),
                                label=s.get("label"),
                            )
                        )
                return StreamResult(
                    url=str(stream["url"]),
                    headers=headers,
                    subtitles=subs,
                    quality=stream.get("quality"),
                )
        return None


class HttpJsonStreamProvider:
    """Configurable live HTTP/JSON StreamProvider."""

    name: str = "Live HTTP Provider"

    def __init__(
        self,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.strip()
        if self.base_url and not self.base_url.endswith("/"):
            self.base_url += "/"
        self.headers = dict(headers or {})
        self.timeout = timeout
        self._transport = transport
        self.last_error: str | None = None

    def _get_json(self, path: str, params: dict[str, str]) -> Any | None:
        if not self.base_url:
            self.last_error = "Live provider base_url is not configured."
            return None
        self.last_error = None
        try:
            with httpx.Client(
                base_url=self.base_url,
                headers=self.headers,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                transport=self._transport,
            ) as client:
                resp = client.get(path, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def search_match(self, title: str) -> str | None:
        target = _normalize_title(title)
        if not target:
            return None
        data = self._get_json("search", {"q": title})
        if data is None:
            return None

        if isinstance(data, dict):
            if data.get("id") and "results" not in data and "data" not in data:
                return str(data["id"])
            items = data.get("results") or data.get("data") or []
        elif isinstance(data, list):
            items = data
        else:
            return None

        if not isinstance(items, list):
            return None

        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            item_title = str(item.get("title") or "")
            if _normalize_title(item_title) == target:
                return str(item["id"])

        for item in items:
            if isinstance(item, dict) and item.get("id"):
                return str(item["id"])
        return None

    def list_episodes(self, series_id: str) -> list[EpisodeInfo]:
        data = self._get_json("episodes", {"id": series_id})
        if data is None:
            return []
        if isinstance(data, dict):
            raw_eps = (
                data.get("episodes")
                or data.get("list")
                or data.get("data")
                or []
            )
        elif isinstance(data, list):
            raw_eps = data
        else:
            return []

        if not isinstance(raw_eps, list):
            return []

        out: list[EpisodeInfo] = []
        for ep in raw_eps:
            if not isinstance(ep, dict):
                continue
            ep_id = str(ep.get("id") or ep.get("number") or "")
            if not ep_id:
                continue
            out.append(
                EpisodeInfo(
                    id=ep_id,
                    number=str(ep.get("number") or ep_id),
                    title=ep.get("title"),
                    is_filler=bool(ep.get("is_filler", False)),
                )
            )
        return out

    def resolve_stream(
        self, series_id: str, episode_id: str
    ) -> StreamResult | None:
        data = self._get_json(
            "stream", {"id": series_id, "episode": episode_id}
        )
        if not isinstance(data, dict):
            return None
        stream = data.get("stream") if isinstance(data.get("stream"), dict) else data
        url = stream.get("url") or stream.get("link")
        if not url:
            return None

        headers = {
            str(k): str(v)
            for k, v in (stream.get("headers") or {}).items()
            if v is not None
        }
        subs: list[SubtitleTrack] = []
        for s in stream.get("subtitles") or []:
            if isinstance(s, dict) and s.get("url"):
                subs.append(
                    SubtitleTrack(
                        url=str(s["url"]),
                        lang=str(s.get("lang") or "und"),
                        label=s.get("label"),
                    )
                )
        return StreamResult(
            url=str(url),
            headers=headers,
            subtitles=subs,
            quality=stream.get("quality"),
        )


def _parse_episodes_list(raw_eps: Any) -> list[EpisodeInfo]:
    if not isinstance(raw_eps, list):
        return []
    out: list[EpisodeInfo] = []
    for ep in raw_eps:
        if not isinstance(ep, dict):
            continue
        ep_id = str(ep.get("id") or ep.get("number") or "")
        if not ep_id:
            continue
        out.append(
            EpisodeInfo(
                id=ep_id,
                number=str(ep.get("number") or ep_id),
                title=ep.get("title"),
                is_filler=bool(ep.get("is_filler", False)),
            )
        )
    return out


def _parse_stream_result(data: Any) -> StreamResult | None:
    if not isinstance(data, dict):
        return None
    stream = data.get("stream") if isinstance(data.get("stream"), dict) else data
    url = stream.get("url") or stream.get("link")
    if not url:
        return None
    headers = {
        str(k): str(v)
        for k, v in (stream.get("headers") or {}).items()
        if v is not None
    }
    subs: list[SubtitleTrack] = []
    for s in stream.get("subtitles") or []:
        if isinstance(s, dict) and s.get("url"):
            subs.append(
                SubtitleTrack(
                    url=str(s["url"]),
                    lang=str(s.get("lang") or "und"),
                    label=s.get("label"),
                )
            )
    audio_urls = [
        str(a) for a in (stream.get("audio_urls") or []) if a
    ]
    single_audio = stream.get("audio_url")
    if isinstance(single_audio, str) and single_audio and single_audio not in audio_urls:
        audio_urls.insert(0, single_audio)
    return StreamResult(
        url=str(url),
        headers=headers,
        subtitles=subs,
        audio_urls=audio_urls,
        quality=stream.get("quality"),
    )


class ResolverCommandProvider:
    """Subprocess-based StreamProvider invoking a local resolver script/executable."""

    name: str = "Resolver Command"

    def __init__(
        self,
        command: list[str] | str | None,
        *,
        timeout: float = 60.0,
    ) -> None:
        if isinstance(command, str):
            self.command: list[str] = (
                shlex.split(command, posix=False) if command.strip() else []
            )
        elif isinstance(command, list):
            self.command = [str(x) for x in command if str(x)]
        else:
            self.command = []
        self.timeout = timeout
        self.last_error: str | None = None
        self._titles_by_id: dict[str, tuple[str, str | None]] = {}

    def _run_json(self, extra_args: list[str]) -> Any | None:
        if not self.command:
            self.last_error = "Resolver command is not configured."
            return None
        self.last_error = None
        run_kwargs: dict[str, Any] = {}
        if sys.platform == "win32":
            run_kwargs["creationflags"] = getattr(
                subprocess, "CREATE_NO_WINDOW", 0x08000000
            )
        try:
            proc = subprocess.run(
                [*self.command, *extra_args],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                **run_kwargs,
            )
        except Exception as exc:
            self.last_error = str(exc)
            return None

        if proc.returncode != 0:
            err = (proc.stderr or "").strip()
            self.last_error = err or f"Resolver exited with code {proc.returncode}"
            return None

        try:
            data = json.loads(proc.stdout)
        except Exception as exc:
            self.last_error = f"Invalid resolver JSON: {exc}"
            return None

        if isinstance(data, dict) and data.get("error"):
            self.last_error = str(data["error"])
        elif isinstance(data, dict) and data.get("stream") is None and proc.stderr:
            err_lines = [ln.strip() for ln in proc.stderr.splitlines() if ln.strip()]
            if err_lines:
                self.last_error = err_lines[-1][:240]
        return data

    def search_match(
        self, title: str, *, alt_title: str | None = None
    ) -> str | None:
        args = ["--title", title]
        if alt_title and alt_title.strip():
            args.extend(["--alt-title", alt_title.strip()])
        data = self._run_json(args)
        if isinstance(data, dict):
            sid = data.get("series_id") or data.get("id")
            if sid:
                sid_str = str(sid)
                self._titles_by_id[sid_str] = (title, alt_title)
                return sid_str
            eps = data.get("episodes")
            if isinstance(eps, list) and eps:
                self._titles_by_id[title] = (title, alt_title)
                return title
        elif isinstance(data, list) and data:
            self._titles_by_id[title] = (title, alt_title)
            return title
        return None

    def list_episodes(
        self,
        series_id: str,
        *,
        title: str | None = None,
        alt_title: str | None = None,
    ) -> list[EpisodeInfo]:
        stored_title, stored_alt = self._titles_by_id.get(
            series_id, (series_id, None)
        )
        eff_title = title or stored_title
        eff_alt = alt_title if alt_title is not None else stored_alt
        if title or alt_title is not None:
            self._titles_by_id[series_id] = (eff_title, eff_alt)
        data = self._run_json(["--series-id", series_id, "--title", eff_title])
        if isinstance(data, dict):
            raw_eps = data.get("episodes") or data.get("list") or data.get("data")
        else:
            raw_eps = data
        return _parse_episodes_list(raw_eps)

    def resolve_stream(
        self,
        series_id: str,
        episode_id: str,
        *,
        title: str | None = None,
        alt_title: str | None = None,
    ) -> StreamResult | None:
        stored_title, stored_alt = self._titles_by_id.get(
            series_id, (series_id, None)
        )
        eff_title = title or stored_title
        eff_alt = alt_title if alt_title is not None else stored_alt
        args = ["--series-id", series_id, "--title", eff_title, "--episode", episode_id]
        if eff_alt and eff_alt.strip():
            args.extend(["--alt-title", eff_alt.strip()])
        data = self._run_json(args)
        return _parse_stream_result(data)


class BundledResolverProvider:
    """In-process StreamProvider for bundled scripts/resolver.py in frozen builds."""

    name: str = "Resolver Command (Bundled)"

    def __init__(self, script_path: Path) -> None:
        self._script_path = script_path
        self.last_error: str | None = None
        self._mod: Any = None
        self._titles_by_id: dict[str, tuple[str, str | None]] = {}

    def _load(self):
        if self._mod is not None:
            return self._mod
        if not self._script_path.is_file():
            raise FileNotFoundError(
                f"Bundled resolver script not found at {self._script_path}"
            )
        spec = importlib.util.spec_from_file_location(
            "anilab_bundled_resolver", self._script_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Cannot load resolver at {self._script_path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self._mod = mod
        return mod

    def search_match(
        self, title: str, *, alt_title: str | None = None
    ) -> str | None:
        self.last_error = None
        try:
            res = self._load().search_and_list_episodes(title, None)
            sid = res.get("series_id")
            if sid:
                sid_str = str(sid)
                self._titles_by_id[sid_str] = (title, alt_title)
                return sid_str
            return None
        except Exception as exc:
            self.last_error = str(exc)
            return None

    def list_episodes(
        self,
        series_id: str,
        *,
        title: str | None = None,
        alt_title: str | None = None,
    ) -> list[EpisodeInfo]:
        self.last_error = None
        stored_title, stored_alt = self._titles_by_id.get(
            series_id, (series_id, None)
        )
        eff_title = title or stored_title
        eff_alt = alt_title if alt_title is not None else stored_alt
        if title or alt_title is not None or series_id not in self._titles_by_id:
            self._titles_by_id[series_id] = (eff_title, eff_alt)
        try:
            res = self._load().search_and_list_episodes(eff_title, series_id)
            return _parse_episodes_list(res.get("episodes"))
        except Exception as exc:
            self.last_error = str(exc)
            return []

    def resolve_stream(
        self,
        series_id: str,
        episode_id: str,
        *,
        title: str | None = None,
        alt_title: str | None = None,
    ) -> StreamResult | None:
        self.last_error = None
        stored_title, stored_alt = self._titles_by_id.get(
            series_id, (series_id, None)
        )
        eff_title = title or stored_title
        eff_alt = alt_title if alt_title is not None else stored_alt
        try:
            fn = self._load().resolve_episode_stream
            if eff_alt and eff_alt.strip():
                res = fn(eff_title, series_id, episode_id, alt_title=eff_alt.strip())
            else:
                res = fn(eff_title, series_id, episode_id)
        except Exception as exc:
            self.last_error = str(exc)
            return None

        parsed = _parse_stream_result(res)
        if parsed is None:
            if isinstance(res, dict) and res.get("error"):
                self.last_error = str(res["error"])
            else:
                self.last_error = (
                    f"No stream returned for '{title}' Ep {episode_id}."
                )
        return parsed


class FallbackStreamProvider:
    """Tries multiple StreamProviders in order and returns the first valid match."""

    name: str = "Auto (Fallback Chain)"

    def __init__(self, providers: list[StreamProvider]) -> None:
        self.providers = list(providers)
        self.last_error: str | None = None

    @staticmethod
    def _encode_id(idx: int, raw_id: str) -> str:
        return f"{idx}:{raw_id}"

    @staticmethod
    def _decode_id(series_id: str) -> tuple[int | None, str]:
        if ":" in series_id:
            prefix, rest = series_id.split(":", 1)
            if prefix.isdigit():
                return int(prefix), rest
        return None, series_id

    def search_match(
        self, title: str, *, alt_title: str | None = None
    ) -> str | None:
        errors: list[str] = []
        for idx, prov in enumerate(self.providers):
            if alt_title and isinstance(
                prov, (ResolverCommandProvider, BundledResolverProvider)
            ):
                sid = prov.search_match(title, alt_title=alt_title)
            else:
                sid = prov.search_match(title)
            if sid:
                self.last_error = None
                return self._encode_id(idx, sid)
            err = getattr(prov, "last_error", None)
            if err:
                errors.append(f"{prov.name}: {err}")
        self.last_error = "; ".join(errors) if errors else None
        return None

    def list_episodes(self, series_id: str) -> list[EpisodeInfo]:
        idx, raw_id = self._decode_id(series_id)
        if idx is not None and 0 <= idx < len(self.providers):
            eps = self.providers[idx].list_episodes(raw_id)
            if eps:
                self.last_error = None
                return eps
            self.last_error = getattr(self.providers[idx], "last_error", None)
            return []

        for prov in self.providers:
            eps = prov.list_episodes(raw_id)
            if eps:
                self.last_error = None
                return eps
        return []

    def resolve_stream(
        self,
        series_id: str,
        episode_id: str,
        *,
        title: str | None = None,
        alt_title: str | None = None,
    ) -> StreamResult | None:
        def _call(prov: StreamProvider, rid: str) -> StreamResult | None:
            if (title is not None or alt_title is not None) and isinstance(
                prov, (ResolverCommandProvider, BundledResolverProvider)
            ):
                return prov.resolve_stream(
                    rid, episode_id, title=title, alt_title=alt_title
                )
            return prov.resolve_stream(rid, episode_id)

        idx, raw_id = self._decode_id(series_id)
        if idx is not None and 0 <= idx < len(self.providers):
            res = _call(self.providers[idx], raw_id)
            if res is not None:
                self.last_error = None
                return res
            self.last_error = getattr(self.providers[idx], "last_error", None)
            return None

        for prov in self.providers:
            res = _call(prov, raw_id)
            if res is not None:
                self.last_error = None
                return res
        return None
