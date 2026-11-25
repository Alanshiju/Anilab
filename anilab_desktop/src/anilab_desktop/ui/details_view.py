"""Anime Details view with clean glassmorphism hero, badges, and playback actions."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from anilab_desktop.models.catalog import AnimeDetails
from anilab_desktop.playback.launcher import (
    LaunchResult,
    is_direct_media_url,
    launch_in_vlc,
    open_url,
)

from .widgets import (
    PosterLoader,
    SmoothScrollArea,
    apply_glass_shadow,
    rounded_pixmap,
)


class DetailsView(QWidget):
    """Displays AnimeDetails, watch progress badges, and playback/provider actions."""

    back_requested = Signal()
    providers_page_requested = Signal(int, str)
    in_app_play_requested = Signal(str, str)
    find_episodes_requested = Signal(str)
    play_next_requested = Signal(int, str, str)
    add_stream_requested = Signal(str)
    provider_changed = Signal(str)

    def __init__(self, poster_loader: PosterLoader, parent=None) -> None:
        super().__init__(parent)
        self._poster_loader = poster_loader
        self._current: AnimeDetails | None = None
        self._player_token: str | None = None
        self._vlc_path: str | None = None
        self._active_provider: str = "json"
        self._last_watched: str | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        top_bar = QFrame()
        top_bar.setObjectName("GlassPanel")
        apply_glass_shadow(top_bar, blur=20, alpha=95)
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(14, 10, 14, 10)
        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self.back_requested.emit)
        self._title = QLabel("Anime Details")
        self._title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        top.addWidget(back_btn)
        top.addWidget(self._title, stretch=1)
        outer.addWidget(top_bar)

        scroll = SmoothScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(14)

        hero = QFrame()
        hero.setObjectName("GlassPanel")
        apply_glass_shadow(hero, blur=24, alpha=105)
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 18, 18, 18)
        hero_layout.setSpacing(18)

        self._poster = QLabel("No Poster")
        self._poster.setFixedSize(188, 262)
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setStyleSheet(
            "background-color: rgba(255,255,255,0.05); border-radius: 12px;"
        )
        hero_layout.addWidget(self._poster)

        info_col = QVBoxLayout()
        info_col.setSpacing(10)

        self._badges_layout = QHBoxLayout()
        self._badges_layout.setSpacing(6)
        info_col.addLayout(self._badges_layout)

        self._synopsis = QTextEdit()
        self._synopsis.setReadOnly(True)
        self._synopsis.setMinimumHeight(190)
        info_col.addWidget(self._synopsis, stretch=1)
        hero_layout.addLayout(info_col, stretch=1)
        layout.addWidget(hero)

        actions_card = QFrame()
        actions_card.setObjectName("GlassPanel")
        apply_glass_shadow(actions_card, blur=20, alpha=95)
        al = QVBoxLayout(actions_card)
        al.setContentsMargins(16, 14, 16, 14)
        al.setSpacing(10)

        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        al.addLayout(self._actions)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet("color: #c4b5fd;")
        al.addWidget(self._status)
        layout.addWidget(actions_card)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, stretch=1)

    def set_details(
        self,
        details: AnimeDetails,
        *,
        player_token: str | None = None,
        vlc_path: str | None = None,
        active_provider: str = "json",
        last_watched: str | None = None,
    ) -> None:
        self._current = details
        self._player_token = player_token
        self._vlc_path = vlc_path
        self._active_provider = active_provider
        self._last_watched = last_watched
        self._title.setText(details.title)

        self._poster.setPixmap(QPixmap())
        self._poster.setText("Loading...")
        poster_url = details.resizedPosterUrl or details.posterUrl
        if poster_url:
            self._poster_loader.load(poster_url, self._set_poster)
        else:
            self._poster.setText("No Poster")

        self._rebuild_badges(details, last_watched)
        self._synopsis.setPlainText(details.synopsis or "(No synopsis available)")
        self._status.setText("")
        self._rebuild_actions(details)

    def _rebuild_badges(
        self, details: AnimeDetails, last_watched: str | None
    ) -> None:
        while self._badges_layout.count():
            item = self._badges_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if details.score:
            sb = QLabel(f"★ {details.score}")
            sb.setObjectName("ScoreBadge")
            self._badges_layout.addWidget(sb)

        if last_watched:
            wb = QLabel(f"Last Watched: Ep {last_watched}")
            wb.setObjectName("WatchedBadge")
            self._badges_layout.addWidget(wb)

        for val in (
            details.type,
            details.status,
            f"{details.episodeCount} eps" if details.episodeCount else None,
            details.premiered,
            details.duration,
        ):
            if val:
                b = QLabel(val)
                b.setObjectName("Badge")
                self._badges_layout.addWidget(b)

        self._badges_layout.addStretch()

    def _set_poster(self, pix: QPixmap) -> None:
        self._poster.setText("")
        self._poster.setPixmap(rounded_pixmap(pix, QSize(188, 262), radius=12))

    def _report_result(self, result: LaunchResult) -> None:
        self._status.setText(result.message)
        if not result.ok:
            QMessageBox.warning(self, "Playback", result.message)

    def _play_in_vlc(self, url: str) -> None:
        if not is_direct_media_url(url):
            self._status.setText(
                "Webpage/embed URL detected; opening inside in-app viewer instead of VLC."
            )
            self.in_app_play_requested.emit(url, self._title.text())
            return
        res = launch_in_vlc(url, vlc_path=self._vlc_path, fallback_to_browser=False)
        self._report_result(res)

    def set_status_message(self, message: str) -> None:
        self._status.setText(message)

    def _rebuild_actions(self, details: AnimeDetails) -> None:
        while self._actions.count():
            item = self._actions.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        next_ep = "1"
        if self._last_watched and self._last_watched.isdigit():
            next_ep = str(int(self._last_watched) + 1)

        next_btn = QPushButton(f"Play Next (Ep {next_ep})")
        next_btn.setObjectName("PrimaryButton")
        next_btn.clicked.connect(
            lambda _=False, aid=details.id, t=details.title, ne=next_ep: self.play_next_requested.emit(
                aid, t, ne
            )
        )
        self._actions.addWidget(next_btn)

        ep_btn = QPushButton("Find / Play Episodes")
        ep_btn.clicked.connect(
            lambda _=False, t=details.title: self.find_episodes_requested.emit(t)
        )
        self._actions.addWidget(ep_btn)

        add_stream_btn = QPushButton("Add / Update Stream")
        add_stream_btn.clicked.connect(
            lambda _=False, t=details.title: self.add_stream_requested.emit(t)
        )
        self._actions.addWidget(add_stream_btn)

        prov_combo = QComboBox()
        prov_combo.addItem("Auto (Fallback)", "auto")
        prov_combo.addItem("Local JSON", "json")
        prov_combo.addItem("Live HTTP", "http")
        prov_combo.addItem("Resolver Command", "command")
        idx = prov_combo.findData(self._active_provider)
        if idx >= 0:
            prov_combo.setCurrentIndex(idx)
        prov_combo.currentIndexChanged.connect(
            lambda _i, cb=prov_combo: self._on_provider_selected(
                str(cb.currentData())
            )
        )
        self._actions.addWidget(prov_combo)

        if details.useProvidersPage:
            btn = QPushButton("Providers")
            btn.clicked.connect(
                lambda: self.providers_page_requested.emit(
                    details.id, details.title
                )
            )
            self._actions.addWidget(btn)

        if details.trailerUrl:
            t_in = QPushButton("Watch Trailer")
            t_in.clicked.connect(
                lambda _=False, u=details.trailerUrl: self.in_app_play_requested.emit(
                    u or "", f"{details.title} — Trailer"
                )
            )
            self._actions.addWidget(t_in)

        for prov in details.providers:
            p_in = QPushButton(f"{prov.name}")
            p_in.clicked.connect(
                lambda _=False, u=prov.url, n=prov.name: self.in_app_play_requested.emit(
                    u, f"{details.title} — {n}"
                )
            )
            self._actions.addWidget(p_in)

            if is_direct_media_url(prov.url):
                p_vlc = QPushButton(f"{prov.name} (VLC)")
                p_vlc.clicked.connect(
                    lambda _=False, u=prov.url: self._play_in_vlc(u)
                )
                self._actions.addWidget(p_vlc)

        self._actions.addStretch()

    def _on_provider_selected(self, key: str) -> None:
        self._active_provider = key
        self.provider_changed.emit(key)
