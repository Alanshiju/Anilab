"""Dialog for picking a StreamingProvider and opening in-app, browser, or VLC."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from anilab_desktop.models.catalog import StreamingProvider
from anilab_desktop.playback.launcher import (
    is_direct_media_url,
    launch_in_vlc,
    open_url,
)


class ProvidersDialog(QDialog):
    """Displays StreamingProvider entries with In-App, Browser, and VLC actions."""

    in_app_requested = Signal(str, str)

    def __init__(
        self,
        title: str,
        providers: list[StreamingProvider],
        parent=None,
        *,
        vlc_path: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._vlc_path = vlc_path
        self.setWindowTitle(f"Providers — {title}")
        self.resize(480, 350)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Select a provider for {title}:"))

        self._list = QListWidget()
        for prov in providers:
            item = QListWidgetItem(f"{prov.name} — {prov.url}")
            item.setData(256, prov.url)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._open_in_app)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        in_app_btn = QPushButton("Open In-App")
        in_app_btn.setObjectName("PrimaryButton")
        in_app_btn.clicked.connect(self._open_in_app)
        open_btn = QPushButton("Open in Browser")
        open_btn.clicked.connect(self._open_selected)
        vlc_btn = QPushButton("Play in VLC")
        vlc_btn.clicked.connect(self._play_selected_in_vlc)
        btns.addWidget(in_app_btn)
        btns.addWidget(open_btn)
        btns.addWidget(vlc_btn)
        layout.addLayout(btns)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

    def _selected_url(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        url = item.data(256)
        return str(url) if url else None

    def _open_in_app(self) -> None:
        url = self._selected_url()
        if url:
            self.in_app_requested.emit(url, self._title)
            self.accept()

    def _open_selected(self) -> None:
        url = self._selected_url()
        if url:
            res = open_url(url)
            self._status.setText(res.message)

    def _play_selected_in_vlc(self) -> None:
        url = self._selected_url()
        if not url:
            return
        if not is_direct_media_url(url):
            self._status.setText(
                "Webpage URLs cannot play in VLC; click 'Open In-App' or 'Open in Browser'."
            )
            return
        res = launch_in_vlc(
            url, vlc_path=self._vlc_path, fallback_to_browser=False
        )
        self._status.setText(res.message)
