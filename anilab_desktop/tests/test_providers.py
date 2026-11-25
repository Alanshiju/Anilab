"""Unit tests for StreamProvider and JsonStreamProvider."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import httpx

from anilab_desktop.playback.providers import (
    FallbackStreamProvider,
    HttpJsonStreamProvider,
    JsonStreamProvider,
    ResolverCommandProvider,
    StreamProvider,
)
from anilab_desktop.state.store import LiveProviderConfig, LocalStore


def test_json_stream_provider_template_and_empty(tmp_path: Path) -> None:
    cfg = tmp_path / "streams.json"
    provider: StreamProvider = JsonStreamProvider(cfg)
    assert provider.search_match("Detective Conan") is None
    assert provider.list_episodes("missing") == []
    assert provider.resolve_stream("missing", "1") is None

    created = provider.ensure_template()
    assert created == cfg
    assert json.loads(cfg.read_text(encoding="utf-8")) == {"series": []}


def test_json_stream_provider_match_list_and_resolve(tmp_path: Path) -> None:
    cfg = tmp_path / "streams.json"
    cfg.write_text(
        json.dumps(
            {
                "series": [
                    {
                        "id": "conan-1230",
                        "title": "Detective Conan",
                        "aliases": ["Case Closed"],
                        "episodes": [
                            {
                                "id": "ep-1",
                                "number": "1",
                                "title": "Roller Coaster Murder Case",
                                "is_filler": False,
                                "stream": {
                                    "url": "https://cdn.example.com/conan/1.m3u8",
                                    "quality": "1080p",
                                    "headers": {
                                        "Referer": "https://provider.example/",
                                        "User-Agent": "AniMeloDesktop/1.0",
                                    },
                                    "subtitles": [
                                        {
                                            "url": "https://cdn.example.com/conan/1.vtt",
                                            "lang": "en",
                                            "label": "English",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    provider = JsonStreamProvider(cfg)
    assert provider.search_match("detective conan!") == "conan-1230"
    assert provider.search_match("Case Closed") == "conan-1230"
    assert provider.search_match("Unknown Show") is None

    eps = provider.list_episodes("conan-1230")
    assert len(eps) == 1
    assert eps[0].id == "ep-1"
    assert eps[0].number == "1"
    assert eps[0].title == "Roller Coaster Murder Case"

    res = provider.resolve_stream("conan-1230", "ep-1")
    assert res is not None
    assert res.url == "https://cdn.example.com/conan/1.m3u8"
    assert res.quality == "1080p"
    assert res.headers["Referer"] == "https://provider.example/"
    assert res.subtitles[0].lang == "en"
    assert res.subtitles[0].url == "https://cdn.example.com/conan/1.vtt"


def test_http_json_stream_provider_mocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "test-key"
        path = request.url.path
        if path.endswith("/search"):
            return httpx.Response(
                200,
                json={"results": [{"id": "s-1", "title": "Detective Conan"}]},
            )
        if path.endswith("/episodes"):
            return httpx.Response(
                200,
                json={
                    "episodes": [
                        {"id": "ep-1", "number": "1", "title": "Episode One"}
                    ]
                },
            )
        if path.endswith("/stream"):
            return httpx.Response(
                200,
                json={
                    "url": "https://cdn.example.com/ep1.m3u8",
                    "quality": "1080p",
                    "headers": {
                        "Referer": "https://live.example/",
                        "User-Agent": "LiveUA/1.0",
                    },
                    "subtitles": [
                        {
                            "url": "https://cdn.example.com/ep1.vtt",
                            "lang": "en",
                            "label": "English",
                        }
                    ],
                },
            )
        return httpx.Response(404)

    provider = HttpJsonStreamProvider(
        "https://live.example/api",
        headers={"X-Api-Key": "test-key"},
        transport=httpx.MockTransport(handler),
    )

    sid = provider.search_match("Detective Conan")
    assert sid == "s-1"

    eps = provider.list_episodes("s-1")
    assert len(eps) == 1
    assert eps[0].id == "ep-1"
    assert eps[0].title == "Episode One"

    stream = provider.resolve_stream("s-1", "ep-1")
    assert stream is not None
    assert stream.url == "https://cdn.example.com/ep1.m3u8"
    assert stream.headers["Referer"] == "https://live.example/"
    assert stream.subtitles[0].url == "https://cdn.example.com/ep1.vtt"
    assert provider.last_error is None


def test_http_json_stream_provider_error_fallbacks(tmp_path: Path) -> None:
    unconfigured = HttpJsonStreamProvider("")
    assert unconfigured.search_match("Conan") is None
    assert unconfigured.last_error is not None

    def fail_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search"):
            return httpx.Response(500, text="server error")
        if request.url.path.endswith("/episodes"):
            return httpx.Response(200, content=b"not-json")
        raise httpx.ConnectError("connection refused", request=request)

    failing = HttpJsonStreamProvider(
        "https://live.example/api/",
        transport=httpx.MockTransport(fail_handler),
    )
    assert failing.search_match("Conan") is None
    assert failing.last_error is not None
    assert failing.list_episodes("s-1") == []
    assert failing.last_error is not None
    assert failing.resolve_stream("s-1", "ep-1") is None
    assert failing.last_error is not None

    store = LocalStore(tmp_path / "state.json")
    store.active_provider = "http"
    store.live_provider = LiveProviderConfig(
        base_url="https://live.example/api/",
        headers={"Authorization": "Bearer abc"},
        timeout=20.0,
    )
    store.save()

    reloaded = LocalStore(tmp_path / "state.json")
    assert reloaded.active_provider == "http"
    assert reloaded.live_provider.base_url == "https://live.example/api/"
    assert reloaded.live_provider.headers["Authorization"] == "Bearer abc"
    assert reloaded.live_provider.timeout == 20.0


def test_json_stream_provider_upsert_preserves_and_updates(tmp_path: Path) -> None:
    cfg = tmp_path / "streams.json"
    cfg.write_text(
        json.dumps(
            {
                "series": [
                    {
                        "id": "existing-show",
                        "title": "Existing Show",
                        "aliases": [],
                        "episodes": [],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    provider = JsonStreamProvider(cfg)
    sid, ep1 = provider.upsert_episode(
        "Detective Conan",
        "1",
        "https://cdn.example.com/1.m3u8",
        episode_title="First Case",
        referer="https://ref.example/",
        user_agent="UA/1.0",
        subtitle_url="https://cdn.example.com/1.vtt",
    )
    assert sid == "detective-conan"
    assert ep1 == "ep-1"

    # Update episode 1 and add episode 2
    sid2, ep1_again = provider.upsert_episode(
        "Detective Conan",
        "1",
        "https://cdn.example.com/1-hd.m3u8",
        episode_title="First Case HD",
    )
    assert sid2 == sid
    assert ep1_again == ep1

    provider.upsert_episode(
        "Detective Conan",
        "2",
        "https://cdn.example.com/2.mp4",
    )

    # Existing series is preserved
    assert provider.search_match("Existing Show") == "existing-show"

    eps = provider.list_episodes(sid)
    assert [e.number for e in eps] == ["1", "2"]
    assert eps[0].title == "First Case HD"

    stream1 = provider.resolve_stream(sid, "ep-1")
    assert stream1 is not None
    assert stream1.url == "https://cdn.example.com/1-hd.m3u8"


def test_resolver_command_provider(tmp_path: Path) -> None:
    script = tmp_path / "resolver.py"
    script.write_text(
        "\n".join(
            [
                "import json, sys",
                "args = sys.argv[1:]",
                "if '--episode' in args:",
                "    print(json.dumps({'stream': {'url': 'https://cdn.example.com/ep1.m3u8', 'headers': {'Referer': 'https://ref.example/'}, 'quality': '1080p'}}))",
                "elif '--series-id' in args:",
                "    print(json.dumps({'episodes': [{'id': 'ep-1', 'number': '1', 'title': 'Start'}]}))",
                "else:",
                "    print(json.dumps({'series_id': 'cmd-123'}))",
            ]
        ),
        encoding="utf-8",
    )

    prov = ResolverCommandProvider([sys.executable, str(script)])
    sid = prov.search_match("Detective Conan")
    assert sid == "cmd-123"
    eps = prov.list_episodes(sid)
    assert len(eps) == 1
    assert eps[0].number == "1"
    stream = prov.resolve_stream(sid, "ep-1")
    assert stream is not None
    assert stream.url == "https://cdn.example.com/ep1.m3u8"
    assert stream.headers["Referer"] == "https://ref.example/"

    unconfigured = ResolverCommandProvider(None)
    assert unconfigured.search_match("X") is None
    assert unconfigured.last_error is not None


def test_fallback_stream_provider_and_watch_progress(tmp_path: Path) -> None:
    empty_json = JsonStreamProvider(tmp_path / "empty.json")
    populated_json = JsonStreamProvider(tmp_path / "populated.json")
    populated_json.upsert_episode(
        "Detective Conan",
        "1",
        "https://cdn.example.com/1.m3u8",
    )

    fallback = FallbackStreamProvider([empty_json, populated_json])
    sid = fallback.search_match("Detective Conan")
    assert sid is not None and sid.startswith("1:")
    eps = fallback.list_episodes(sid)
    assert len(eps) == 1
    stream = fallback.resolve_stream(sid, eps[0].id)
    assert stream is not None
    assert stream.url == "https://cdn.example.com/1.m3u8"

    store = LocalStore(tmp_path / "state.json")
    store.resolver_command = ["python", "resolver.py"]
    store.set_last_watched("3", anime_id=1230, title="Detective Conan")

    reloaded = LocalStore(tmp_path / "state.json")
    assert reloaded.resolver_command == ["python", "resolver.py"]
    assert reloaded.get_last_watched(1230, "Detective Conan") == "3"


def _load_resolver_module():
    resolver_path = Path(__file__).resolve().parents[1] / "scripts" / "resolver.py"
    spec = importlib.util.spec_from_file_location("anilab_resolver_script", resolver_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_resolver_script_upstream_mock() -> None:
    resolver = _load_resolver_module()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/search"):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "other-1", "title": "Conan Movie"},
                        {"id": "conan-tv", "title": "Detective Conan"},
                    ]
                },
            )
        if path.endswith("/episodes"):
            return httpx.Response(
                200,
                json={
                    "episodes": [
                        {"id": "ep-1", "number": 1, "title": "Pilot", "isFiller": False}
                    ]
                },
            )
        if path.endswith("/watch"):
            return httpx.Response(
                200,
                json={
                    "headers": {
                        "Referer": "https://upstream.example/",
                        "User-Agent": "ResolverUA/1.0",
                    },
                    "sources": [
                        {"url": "https://cdn.example.com/480.m3u8", "quality": "480p", "isM3U8": True},
                        {"url": "https://cdn.example.com/1080.m3u8", "quality": "1080p", "isM3U8": True},
                    ],
                    "subtitles": [
                        {"url": "https://cdn.example.com/en.vtt", "lang": "en", "label": "English"}
                    ],
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    ep_res = resolver.search_and_list_episodes(
        "Detective Conan",
        None,
        base_url="https://upstream.example",
        transport=transport,
    )
    assert ep_res["series_id"] == "conan-tv"
    assert ep_res["episodes"] == [
        {"id": "ep-1", "number": "1", "title": "Pilot", "is_filler": False}
    ]

    stream_res = resolver.resolve_episode_stream(
        "Detective Conan",
        "conan-tv",
        "ep-1",
        base_url="https://upstream.example",
        transport=transport,
    )
    stream = stream_res["stream"]
    assert stream is not None
    assert stream["url"] == "https://cdn.example.com/1080.m3u8"
    assert stream["quality"] == "1080p"
    assert stream["headers"]["Referer"] == "https://upstream.example/"
    assert stream["headers"]["User-Agent"] == "ResolverUA/1.0"
    assert stream["subtitles"][0]["url"] == "https://cdn.example.com/en.vtt"


def test_resolver_script_offline_returns_null_stream(capsys) -> None:
    resolver = _load_resolver_module()

    def offline_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    res = resolver.resolve_episode_stream(
        "Detective Conan",
        "conan-tv",
        "ep-1",
        base_url="http://127.0.0.1:9999",
        transport=httpx.MockTransport(offline_handler),
    )
    assert res == {"stream": None}
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "HTTP error" in captured.err or "Upstream unavailable" in captured.err
