"""Playback launcher for provider URLs, VLC desktop playback, and Android launchExtras."""

from __future__ import annotations

import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from anilab_desktop.models.config import AnimePlayerConfig
from anilab_desktop.playback.providers import StreamResult

COMMON_WINDOWS_VLC_PATHS: tuple[Path, ...] = (
    Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"),
)

DIRECT_MEDIA_EXTENSIONS: tuple[str, ...] = (
    ".m3u8",
    ".mp4",
    ".mkv",
    ".webm",
    ".mpd",
    ".avi",
    ".mov",
    ".ts",
    ".flv",
)


@dataclass(frozen=True)
class LaunchResult:
    ok: bool
    message: str


def is_direct_media_url(url: str) -> bool:
    """Return True if url looks like a direct media stream/file rather than a webpage."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if any(
        yt in host
        for yt in ("youtube.com", "youtu.be", "youtube-nocookie.com")
    ):
        return False
    path_lower = parsed.path.lower()
    return path_lower.endswith(DIRECT_MEDIA_EXTENSIONS)


def normalize_in_app_url(url: str) -> str:
    """Convert YouTube watch/short URLs to clean embed URLs for QWebEngineView."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    if "youtu.be" in host:
        vid = parsed.path.strip("/").split("/")[0]
        if vid:
            return f"https://www.youtube.com/embed/{vid}?autoplay=1"
    if "youtube.com" in host and parsed.path == "/watch":
        vid = parse_qs(parsed.query).get("v", [""])[0]
        if vid:
            return f"https://www.youtube.com/embed/{vid}?autoplay=1"
    return url


def open_url(url: str) -> LaunchResult:
    """Open a StreamingProvider or trailer URL in the default desktop browser."""
    if not url:
        return LaunchResult(False, "No URL provided.")
    opened = webbrowser.open(url)
    if opened:
        return LaunchResult(True, f"Opened in browser: {url}")
    return LaunchResult(False, f"Could not open browser for: {url}")


def find_vlc_executable(
    vlc_path: str | None = None,
    *,
    common_paths: tuple[Path, ...] = COMMON_WINDOWS_VLC_PATHS,
) -> str | None:
    """Locate vlc.exe via explicit override, PATH, or common Windows install dirs."""
    if vlc_path:
        candidate = Path(vlc_path)
        if candidate.is_file():
            return str(candidate)
        on_path = shutil.which(vlc_path)
        if on_path:
            return on_path

    for name in ("vlc", "vlc.exe"):
        found = shutil.which(name)
        if found:
            return found

    for path in common_paths:
        if path.is_file():
            return str(path)

    return None


def build_vlc_command(
    vlc_exe: str,
    target: str,
    headers: dict[str, str] | None = None,
    *,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Construct the VLC CLI invocation with optional HTTP referrer/user-agent."""
    cmd = [vlc_exe]
    if headers:
        lowered = {k.lower(): v for k, v in headers.items() if v}
        referer = lowered.get("referer") or lowered.get("referrer")
        if referer:
            cmd.append(f"--http-referrer={referer}")
        user_agent = lowered.get("user-agent")
        if user_agent:
            cmd.append(f"--http-user-agent={user_agent}")
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(target)
    return cmd


def launch_in_vlc(
    target: str,
    headers: dict[str, str] | None = None,
    *,
    vlc_path: str | None = None,
    fallback_to_browser: bool = False,
    allow_webpage_in_vlc: bool = False,
    extra_args: list[str] | None = None,
) -> LaunchResult:
    """Launch VLC non-blocking for direct media streams; guard against webpage URLs."""
    if not target:
        return LaunchResult(False, "No target URL provided.")

    if not allow_webpage_in_vlc and not is_direct_media_url(target):
        if fallback_to_browser:
            res = open_url(target)
            if res.ok:
                return LaunchResult(
                    True,
                    "Webpage/embed URLs cannot play directly in VLC; opened in browser: "
                    f"{target}",
                )
            return LaunchResult(
                False,
                "Target is a webpage/embed URL (not a direct stream) and browser fallback failed.",
            )
        return LaunchResult(
            False,
            "Target is a webpage/embed URL, not a direct media stream "
            "(.m3u8/.mp4/.mkv/.webm/.mpd). Use the in-app viewer or browser.",
        )

    vlc_exe = find_vlc_executable(vlc_path)
    if vlc_exe is None:
        if fallback_to_browser:
            res = open_url(target)
            if res.ok:
                return LaunchResult(
                    True, f"VLC not found; opened in browser instead: {target}"
                )
            return LaunchResult(
                False,
                "VLC not found and browser fallback failed. "
                "Set 'vlc_path' in ~/.anilab_desktop/state.json.",
            )
        return LaunchResult(
            False,
            "VLC not found on PATH or in VideoLAN install folders. "
            "Set 'vlc_path' in ~/.anilab_desktop/state.json.",
        )

    cmd = build_vlc_command(vlc_exe, target, headers, extra_args=extra_args)
    try:
        subprocess.Popen(cmd)
        return LaunchResult(True, f"Launched VLC ({vlc_exe}) for: {target}")
    except OSError as exc:
        if fallback_to_browser:
            res = open_url(target)
            if res.ok:
                return LaunchResult(
                    True,
                    f"VLC launch failed ({exc}); opened in browser: {target}",
                )
        return LaunchResult(False, f"Failed to launch VLC: {exc}")


def launch_stream_result(
    result: StreamResult,
    *,
    vlc_path: str | None = None,
) -> LaunchResult:
    """Launch a resolved StreamResult in VLC, attaching headers and default subtitle."""
    extra_args: list[str] = []
    if result.subtitles:
        extra_args.append(f"--sub-file={result.subtitles[0].url}")
    return launch_in_vlc(
        result.url,
        headers=result.headers,
        vlc_path=vlc_path,
        fallback_to_browser=False,
        extra_args=extra_args or None,
    )


def open_desktop_player(
    media_url: str,
    preferred_player: str | None = None,
    *,
    vlc_path: str | None = None,
) -> LaunchResult:
    """Launch VLC (or preferred_player / mpv) if available, else open in browser."""
    if not media_url:
        return LaunchResult(False, "No media URL provided.")
    if preferred_player is None or preferred_player.lower() in {"vlc", "vlc.exe"}:
        return launch_in_vlc(
            media_url, vlc_path=vlc_path, fallback_to_browser=True
        )
    resolved = shutil.which(preferred_player)
    if resolved:
        subprocess.Popen([resolved, media_url])
        return LaunchResult(True, f"Launched {preferred_player} for {media_url}")
    return open_url(media_url)


def format_player_launch_summary(
    player: AnimePlayerConfig | None,
    *,
    player_token: str | None = None,
) -> str:
    """Format KYOTO Player target & launchExtras for display on desktop."""
    if player is None:
        return "No external player configuration provided for this title."

    app_name = player.appName or "External Player"
    pkg = player.androidPackageId or "(unknown package)"
    act = player.androidActivity or "(unknown activity)"
    extras = dict(player.launchExtras)
    extras.setdefault("USER_TOKEN", "<present>" if player_token else "<empty>")

    lines = [
        f"Target App: {app_name} (Android package: {pkg})",
        f"Activity: {act}",
        "Launch Extras (passed via Android Intent):",
    ]
    for k, v in extras.items():
        lines.append(f"  - {k}: {v}")
    lines.append(
        "\nNote: Full episode streams are resolved and played inside the Android "
        f"{app_name} app ({pkg}) rather than returned by the catalog API. "
        "On desktop, you can watch trailers or open provider pages in-app or in your browser."
    )
    return "\n".join(lines)
