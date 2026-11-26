"""Dialog for selecting an episode from the active StreamProvider."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from anilab_desktop.playback.providers import EpisodeInfo

from .widgets import apply_windows_dwm_style


class EpisodesDialog(QDialog):
    """Displays EpisodeInfo items and emits episode_selected(series_id, episode_id)."""

    episode_selected = Signal(str, str)

    def __init__(
        self,
        title: str,
        series_id: str,
        episodes: list[EpisodeInfo],
        parent=None,
        *,
        alt_title: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._alt_title = alt_title
        self._series_id = series_id
        self._dwm_applied = False
        self.setWindowTitle(f"Episodes — {title}")
        self.resize(480, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        hdr = QLabel(f"Select an episode for {title}")
        hdr.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        layout.addWidget(hdr)

        self._list = QListWidget()
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        for ep in episodes:
            label = f"Ep {ep.number}"
            if ep.title:
                label += f" — {ep.title}"
            if ep.is_filler:
                label += " [Filler]"
            item = QListWidgetItem(label)
            item.setData(256, ep.id)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._on_play)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        play_btn = QPushButton("Play Episode")
        play_btn.setObjectName("PrimaryButton")
        play_btn.clicked.connect(self._on_play)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(close_btn)
        btns.addWidget(play_btn)
        layout.addLayout(btns)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._dwm_applied:
            self._dwm_applied = True
            apply_windows_dwm_style(self)

    def _on_play(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        ep_id = item.data(256)
        if ep_id:
            self.episode_selected.emit(self._series_id, str(ep_id))
            self.accept()
