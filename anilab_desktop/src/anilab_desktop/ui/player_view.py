"""In-app QWebEngineView playback/viewer panel for trailers and provider pages."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from anilab_desktop.playback.launcher import (
    is_direct_media_url,
    launch_in_vlc,
    normalize_in_app_url,
    open_url,
)


class PlayerView(QWidget):
    """Embedded browser/player view for trailers and provider pages."""

    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._raw_url: str = ""
        self._vlc_path: str | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("GlassPanel")
        hbar = QHBoxLayout(header)
        hbar.setContentsMargins(12, 8, 12, 8)

        back_btn = QPushButton("← Back")
        back_btn.clicked.connect(self._on_back)
        self._title_lbl = QLabel("In-App Viewer")
        self._title_lbl.setStyleSheet("font-weight: 700; font-size: 14px;")

        self._browser_btn = QPushButton("Pop Out to Browser")
        self._browser_btn.clicked.connect(self._pop_out_browser)

        self._vlc_btn = QPushButton("Play in VLC")
        self._vlc_btn.clicked.connect(self._open_vlc)

        hbar.addWidget(back_btn)
        hbar.addWidget(self._title_lbl, stretch=1)
        hbar.addWidget(self._browser_btn)
        hbar.addWidget(self._vlc_btn)
        layout.addWidget(header)

        self._web = QWebEngineView()
        self._web.setStyleSheet("border-radius: 12px;")
        layout.addWidget(self._web, stretch=1)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    def load_url(
        self, url: str, *, title: str = "", vlc_path: str | None = None
    ) -> None:
        self._raw_url = url
        self._vlc_path = vlc_path
        embed_url = normalize_in_app_url(url)
        self._title_lbl.setText(title or url)
        self._vlc_btn.setEnabled(is_direct_media_url(url))
        self._status.setText(f"Loaded in-app: {embed_url}")
        self._web.setUrl(QUrl(embed_url))

    def _on_back(self) -> None:
        self._web.setUrl(QUrl("about:blank"))
        self.back_requested.emit()

    def _pop_out_browser(self) -> None:
        if self._raw_url:
            res = open_url(self._raw_url)
            self._status.setText(res.message)

    def _open_vlc(self) -> None:
        if self._raw_url:
            res = launch_in_vlc(
                self._raw_url,
                vlc_path=self._vlc_path,
                fallback_to_browser=False,
            )
            self._status.setText(res.message)
