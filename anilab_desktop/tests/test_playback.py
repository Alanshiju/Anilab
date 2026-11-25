"""Unit tests for VLC path resolution, command building, and launcher."""

from __future__ import annotations

from pathlib import Path

from anilab_desktop.playback import launcher
from anilab_desktop.playback.providers import StreamResult, SubtitleTrack
from anilab_desktop.state.store import LocalStore


def test_find_vlc_override_and_common_paths(tmp_path: Path, monkeypatch) -> None:
    custom_vlc = tmp_path / "vlc.exe"
    custom_vlc.write_bytes(b"")

    assert launcher.find_vlc_executable(str(custom_vlc)) == str(custom_vlc)

    monkeypatch.setattr(launcher.shutil, "which", lambda _name: None)
    common_vlc = tmp_path / "VideoLAN" / "vlc.exe"
    common_vlc.parent.mkdir()
    common_vlc.write_bytes(b"")

    assert (
        launcher.find_vlc_executable(common_paths=(common_vlc,))
        == str(common_vlc)
    )
    assert launcher.find_vlc_executable(common_paths=()) is None


def test_build_vlc_command_with_headers() -> None:
    cmd = launcher.build_vlc_command(
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        "https://example.com/video.m3u8",
        headers={
            "Referer": "https://animelo.to/",
            "User-Agent": "AniMeloDesktop/1.0",
        },
    )
    assert cmd == [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        "--http-referrer=https://animelo.to/",
        "--http-user-agent=AniMeloDesktop/1.0",
        "https://example.com/video.m3u8",
    ]


def test_launch_in_vlc_non_blocking(tmp_path: Path, monkeypatch) -> None:
    fake_vlc = tmp_path / "vlc.exe"
    fake_vlc.write_bytes(b"")

    launched: list[list[str]] = []

    def fake_popen(cmd, *args, **kwargs):
        launched.append(cmd)
        return object()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)

    res = launcher.launch_in_vlc(
        "https://example.com/trailer.mp4",
        headers={"Referer": "https://example.com/"},
        vlc_path=str(fake_vlc),
    )
    assert res.ok is True
    assert launched == [
        [
            str(fake_vlc),
            "--http-referrer=https://example.com/",
            "https://example.com/trailer.mp4",
        ]
    ]


def test_launch_in_vlc_missing_and_fallback(monkeypatch) -> None:
    monkeypatch.setattr(launcher, "find_vlc_executable", lambda *_a, **_kw: None)

    res = launcher.launch_in_vlc("https://example.com/video.mp4")
    assert res.ok is False
    assert "vlc_path" in res.message

    opened: list[str] = []
    monkeypatch.setattr(launcher.webbrowser, "open", lambda u: opened.append(u) or True)
    res_fb = launcher.launch_in_vlc(
        "https://www.crunchyroll.com/", fallback_to_browser=True
    )
    assert res_fb.ok is True
    assert opened == ["https://www.crunchyroll.com/"]


def test_direct_media_url_guard_and_youtube_normalization() -> None:
    assert launcher.is_direct_media_url("https://cdn.example.com/stream/master.m3u8?token=1")
    assert launcher.is_direct_media_url("https://cdn.example.com/video.mp4")
    assert not launcher.is_direct_media_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert not launcher.is_direct_media_url("https://www.crunchyroll.com/series-1")

    res = launcher.launch_in_vlc("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert res.ok is False
    assert "webpage/embed" in res.message

    assert (
        launcher.normalize_in_app_url("https://www.youtube.com/watch?v=abc123")
        == "https://www.youtube.com/embed/abc123?autoplay=1"
    )
    assert (
        launcher.normalize_in_app_url("https://youtu.be/xyz789")
        == "https://www.youtube.com/embed/xyz789?autoplay=1"
    )


def test_launch_stream_result_with_headers_and_subtitles(
    tmp_path: Path, monkeypatch
) -> None:
    fake_vlc = tmp_path / "vlc.exe"
    fake_vlc.write_bytes(b"")

    launched: list[list[str]] = []
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        lambda cmd, *a, **kw: launched.append(cmd) or object(),
    )

    stream = StreamResult(
        url="https://cdn.example.com/master.m3u8",
        headers={
            "Referer": "https://provider.example/",
            "User-Agent": "CustomUA/1.0",
        },
        subtitles=[
            SubtitleTrack(
                url="https://cdn.example.com/en.vtt", lang="en", label="English"
            )
        ],
        quality="1080p",
    )
    res = launcher.launch_stream_result(stream, vlc_path=str(fake_vlc))
    assert res.ok is True
    assert launched == [
        [
            str(fake_vlc),
            "--http-referrer=https://provider.example/",
            "--http-user-agent=CustomUA/1.0",
            "--sub-file=https://cdn.example.com/en.vtt",
            "https://cdn.example.com/master.m3u8",
        ]
    ]


def test_store_persists_vlc_path(tmp_path: Path) -> None:
    store = LocalStore(tmp_path / "state.json")
    store.vlc_path = r"D:\Apps\VLC\vlc.exe"
    store.save()

    reloaded = LocalStore(tmp_path / "state.json")
    assert reloaded.vlc_path == r"D:\Apps\VLC\vlc.exe"
