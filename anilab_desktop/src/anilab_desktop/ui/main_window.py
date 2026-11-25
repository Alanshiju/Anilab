"""Main PySide6 window with glassmorphism navigation shell and async workers."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from anilab_desktop.api.client import create_catalog_client
from anilab_desktop.playback.launcher import launch_stream_result
from anilab_desktop.playback.providers import (
    FallbackStreamProvider,
    HttpJsonStreamProvider,
    JsonStreamProvider,
    ResolverCommandProvider,
    StreamProvider,
)
from anilab_desktop.state.store import LocalStore

from .add_stream_dialog import AddStreamDialog
from .details_view import DetailsView
from .episodes_dialog import EpisodesDialog
from .home_view import HomeView, SearchBrowseView
from .player_view import PlayerView
from .providers_dialog import ProvidersDialog
from .widgets import APP_STYLESHEET, PosterLoader, apply_glass_shadow


class _Worker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], Any], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Top-level AniLab Desktop window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AniLab Desktop")
        self.resize(1100, 760)
        self.setStyleSheet(APP_STYLESHEET)

        self._store = LocalStore()
        self._client = create_catalog_client()
        self._poster_loader = PosterLoader(self)
        self._workers: list[_Worker] = []

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)
        self.setCentralWidget(root)

        nav = QFrame()
        nav.setObjectName("GlassNav")
        apply_glass_shadow(nav, blur=22, alpha=105)
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(16, 10, 16, 10)
        nav_layout.setSpacing(10)

        brand = QLabel("AniLab Desktop")
        brand.setStyleSheet("font-size: 16px; font-weight: 700; color: #f9fafb;")
        nav_layout.addWidget(brand)
        nav_layout.addSpacing(12)

        self._nav_home = QPushButton("Home")
        self._nav_home.setObjectName("NavButton")
        self._nav_home.setProperty("active", True)
        self._nav_home.clicked.connect(lambda: self._switch_top_view("home"))

        self._nav_search = QPushButton("Search / Browse")
        self._nav_search.setObjectName("NavButton")
        self._nav_search.setProperty("active", False)
        self._nav_search.clicked.connect(lambda: self._switch_top_view("search"))

        nav_layout.addWidget(self._nav_home)
        nav_layout.addWidget(self._nav_search)
        nav_layout.addStretch()
        root_layout.addWidget(nav)

        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, stretch=1)

        self._home_view = HomeView(self._poster_loader)
        self._search_view = SearchBrowseView(self._poster_loader)
        self._details_view = DetailsView(self._poster_loader)
        self._player_view = PlayerView()

        self._stack.addWidget(self._home_view)
        self._stack.addWidget(self._search_view)
        self._stack.addWidget(self._details_view)
        self._stack.addWidget(self._player_view)

        self._home_view.refresh_requested.connect(self._load_home)
        self._home_view.anime_selected.connect(self._open_details)
        self._search_view.search_requested.connect(self._do_search)
        self._search_view.browse_requested.connect(self._do_browse)
        self._search_view.anime_selected.connect(self._open_details)
        self._details_view.back_requested.connect(
            lambda: self._switch_top_view(self._last_top_view)
        )
        self._details_view.providers_page_requested.connect(self._open_providers)
        self._details_view.in_app_play_requested.connect(self._open_in_app_player)
        self._details_view.find_episodes_requested.connect(self._find_episodes)
        self._details_view.play_next_requested.connect(self._play_next_episode)
        self._details_view.add_stream_requested.connect(self._add_or_update_stream)
        self._details_view.provider_changed.connect(self._on_provider_changed)
        self._player_view.back_requested.connect(
            lambda: self._stack.setCurrentWidget(self._details_view)
        )

        self._last_top_view = "home"
        self._load_home()

    def _switch_top_view(self, target: str) -> None:
        self._last_top_view = target
        is_home = target == "home"
        self._nav_home.setProperty("active", is_home)
        self._nav_search.setProperty("active", not is_home)
        for btn in (self._nav_home, self._nav_search):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._stack.setCurrentWidget(
            self._home_view if is_home else self._search_view
        )

    def _run_async(
        self,
        fn: Callable[[], Any],
        on_ok: Callable[[Any], None],
        on_err: Callable[[str], None] | None = None,
    ) -> None:
        worker = _Worker(fn, self)
        self._workers.append(worker)
        worker.finished_ok.connect(on_ok)
        worker.failed.connect(on_err or self._show_error)
        worker.finished.connect(lambda: self._workers.remove(worker))
        worker.start()

    def _show_error(self, msg: str) -> None:
        QMessageBox.warning(self, "API Error", msg)

    def _load_home(self) -> None:
        self._home_view.set_status("Loading catalog from Jikan...")
        self._run_async(
            self._client.get_home,
            self._home_view.set_home,
            on_err=lambda msg: self._home_view.set_status(
                f"Catalog unavailable (offline or rate-limited): {msg}"
            ),
        )

    def _do_search(self, query: str) -> None:
        self._run_async(
            lambda: self._client.search(query, page=1),
            lambda res: self._search_view.set_results(f"Search '{query}'", res.data),
        )

    def _do_browse(self) -> None:
        self._run_async(
            lambda: self._client.browse(page=1),
            lambda res: self._search_view.set_results("Browse", res.data),
        )

    def _open_details(self, anime_id: int) -> None:
        def _on_loaded(details) -> None:
            self._current_anime_id = details.id
            self._current_anime_title = details.title
            self._details_view.set_details(
                details,
                player_token=self._store.get_player_token(),
                vlc_path=self._store.vlc_path,
                active_provider=self._store.active_provider,
                last_watched=self._store.get_last_watched(
                    details.id, details.title
                ),
            )
            self._stack.setCurrentWidget(self._details_view)

        self._run_async(
            lambda: self._client.get_anime_details(anime_id), _on_loaded
        )

    def _open_providers(self, anime_id: int, title: str) -> None:
        def _show(res) -> None:
            dlg = ProvidersDialog(
                title, res.providers, self, vlc_path=self._store.vlc_path
            )
            dlg.in_app_requested.connect(self._open_in_app_player)
            dlg.exec()

        self._run_async(lambda: self._client.get_anime_providers(anime_id), _show)

    def _open_in_app_player(self, url: str, title: str) -> None:
        self._player_view.load_url(
            url, title=title, vlc_path=self._store.vlc_path
        )
        self._stack.setCurrentWidget(self._player_view)

    def _get_active_provider(self) -> StreamProvider:
        key = self._store.active_provider
        json_prov = JsonStreamProvider(self._store.get_streams_path())
        lp = self._store.live_provider
        http_prov = HttpJsonStreamProvider(
            lp.base_url, headers=lp.headers, timeout=lp.timeout
        )
        cmd_prov = ResolverCommandProvider(
            self._store.resolver_command, timeout=self._store.resolver_timeout
        )

        if key == "auto":
            chain: list[StreamProvider] = [json_prov]
            if lp.base_url.strip():
                chain.append(http_prov)
            if cmd_prov.command:
                chain.append(cmd_prov)
            return FallbackStreamProvider(chain)
        if key == "http":
            return http_prov
        if key == "command":
            return cmd_prov
        return json_prov

    def _on_provider_changed(self, key: str) -> None:
        self._store.active_provider = key
        self._store.save()
        self._details_view.set_status_message(
            f"Switched episode source to: {self._get_active_provider().name}"
        )

    def _add_or_update_stream(self, title: str) -> None:
        dlg = AddStreamDialog(title, self)
        if dlg.exec() != AddStreamDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        json_provider = JsonStreamProvider(self._store.get_streams_path())
        try:
            series_id, ep_id = json_provider.upsert_episode(
                title,
                vals["episode_number"],
                vals["stream_url"],
                episode_title=vals["episode_title"] or None,
                referer=vals["referer"] or None,
                user_agent=vals["user_agent"] or None,
                subtitle_url=vals["subtitle_url"] or None,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Save Stream Error", str(exc))
            return

        if self._store.active_provider != "json":
            self._store.active_provider = "json"
            self._store.save()
        self._details_view.set_status_message(
            f"Saved {series_id} / {ep_id} to {json_provider.config_path}"
        )
        self._find_episodes(title)

    def _find_episodes(self, title: str) -> None:
        provider = self._get_active_provider()
        if (
            isinstance(provider, HttpJsonStreamProvider)
            and not provider.base_url
        ):
            msg = (
                "Live HTTP provider is selected, but 'live_provider.base_url' "
                f"is empty in {self._store.path}."
            )
            self._details_view.set_status_message(msg)
            QMessageBox.information(self, "Live Provider", msg)
            return

        self._details_view.set_status_message(
            f"Searching '{title}' via {provider.name}..."
        )

        def _search():
            if isinstance(provider, JsonStreamProvider):
                provider.ensure_template()
            series_id = provider.search_match(title)
            if not series_id:
                return None, []
            return series_id, provider.list_episodes(series_id)

        def _on_done(res) -> None:
            series_id, episodes = res
            if not series_id or not episodes:
                err = getattr(provider, "last_error", None)
                if err:
                    msg = f"{provider.name} error: {err}"
                else:
                    msg = (
                        f"No episodes returned for '{title}' by {provider.name}.\n\n"
                        f"• Click 'Add / Update Stream' to save a stream to {self._store.get_streams_path()}, or\n"
                        "• Set ANILAB_UPSTREAM_URL to a running REST anime API before launching."
                    )
                self._details_view.set_status_message(msg)
                QMessageBox.information(self, "No Episodes Found", msg)
                return
            dlg = EpisodesDialog(title, series_id, episodes, self)
            dlg.episode_selected.connect(
                lambda sid, eid, eps=episodes: self._resolve_and_play_episode(
                    sid, eid, eps
                )
            )
            dlg.exec()

        self._run_async(_search, _on_done)

    def _play_next_episode(
        self, anime_id: int, title: str, next_ep: str
    ) -> None:
        provider = self._get_active_provider()
        self._details_view.set_status_message(
            f"Auto-resolving Ep {next_ep} for '{title}' via {provider.name}..."
        )

        def _resolve():
            sid = provider.search_match(title)
            if not sid:
                return None, None, None
            eps = provider.list_episodes(sid)
            if not eps:
                return sid, None, None
            chosen = next(
                (e for e in eps if e.number == next_ep or e.id == next_ep),
                eps[0],
            )
            stream = provider.resolve_stream(sid, chosen.id)
            return sid, chosen, stream

        def _on_done(res) -> None:
            _sid, chosen, stream_res = res
            if chosen is None or stream_res is None:
                err = getattr(provider, "last_error", None)
                if err:
                    msg = f"{provider.name} error: {err}"
                else:
                    msg = (
                        f"Could not auto-resolve Ep {next_ep} for '{title}' via {provider.name}.\n\n"
                        f"• Click 'Add / Update Stream' to add an episode URL to {self._store.get_streams_path()}, or\n"
                        "• Point ANILAB_UPSTREAM_URL to an external anime stream API."
                    )
                self._details_view.set_status_message(msg)
                QMessageBox.information(self, "Play Next", msg)
                return
            launch_res = launch_stream_result(
                stream_res, vlc_path=self._store.vlc_path
            )
            if launch_res.ok:
                self._store.set_last_watched(
                    chosen.number, anime_id=anime_id, title=title
                )
            self._details_view.set_status_message(launch_res.message)
            if not launch_res.ok:
                QMessageBox.warning(self, "VLC Playback", launch_res.message)

        self._run_async(_resolve, _on_done)

    def _resolve_and_play_episode(
        self, series_id: str, episode_id: str, episodes=None
    ) -> None:
        provider = self._get_active_provider()
        self._details_view.set_status_message(
            f"Resolving stream for episode {episode_id}..."
        )

        def _on_resolved(stream_res) -> None:
            if stream_res is None:
                err = getattr(provider, "last_error", None)
                msg = (
                    f"{provider.name} error: {err}"
                    if err
                    else f"No stream returned for episode {episode_id} by {provider.name}."
                )
                self._details_view.set_status_message(msg)
                QMessageBox.warning(self, "Stream Error", msg)
                return
            launch_res = launch_stream_result(
                stream_res, vlc_path=self._store.vlc_path
            )
            if launch_res.ok:
                ep_num = episode_id
                if episodes:
                    match = next((e for e in episodes if e.id == episode_id), None)
                    if match is not None:
                        ep_num = match.number
                self._store.set_last_watched(
                    ep_num,
                    anime_id=getattr(self, "_current_anime_id", None),
                    title=getattr(self, "_current_anime_title", None),
                )
            self._details_view.set_status_message(launch_res.message)
            if not launch_res.ok:
                QMessageBox.warning(self, "VLC Playback", launch_res.message)

        self._run_async(
            lambda: provider.resolve_stream(series_id, episode_id),
            _on_resolved,
        )

    def closeEvent(self, event) -> None:
        self._client.close()
        super().closeEvent(event)


def run_app() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
