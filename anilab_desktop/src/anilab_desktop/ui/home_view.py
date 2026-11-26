"""Minimal two-section Home (Latest Episodes) and Search views."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from anilab_desktop.models.catalog import AnimeSummary, HomeResponse

from .widgets import AnimeCard, FlowLayout, PosterLoader, SmoothScrollArea


class HomeView(QWidget):
    """Displays the Latest Episodes grid with smooth scrolling."""

    anime_selected = Signal(int)
    refresh_requested = Signal()

    def __init__(self, poster_loader: PosterLoader, parent=None) -> None:
        super().__init__(parent)
        self._poster_loader = poster_loader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("GlassPanel")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(14, 10, 14, 10)
        self._status = QLabel("Latest Episodes")
        self._status.setStyleSheet("font-weight: 700; font-size: 14px;")
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        top.addWidget(self._status)
        top.addStretch()
        top.addWidget(refresh_btn)
        layout.addWidget(top_bar)

        self._scroll = SmoothScrollArea()
        self._container = QWidget()
        self._flow = FlowLayout(self._container, margin=10, spacing=16)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, stretch=1)

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def set_home(self, home: HomeResponse) -> None:
        while self._flow.count():
            it = self._flow.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()

        items: list[AnimeSummary] = []
        if home.sections:
            first_key = next(iter(home.sections))
            items = home.sections[first_key]
        if not items:
            items = home.spotlight

        for item in items:
            card = AnimeCard(item, self._poster_loader, self._container)
            card.clicked.connect(self.anime_selected.emit)
            self._flow.addWidget(card)

        self._status.setText(f"Latest Episodes ({len(items)})")


class SearchBrowseView(QWidget):
    """Search tab displaying responsive anime card grids."""

    search_requested = Signal(str)
    browse_requested = Signal()
    anime_selected = Signal(int)

    def __init__(self, poster_loader: PosterLoader, parent=None) -> None:
        super().__init__(parent)
        self._poster_loader = poster_loader
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        bar_frame = QFrame()
        bar_frame.setObjectName("GlassPanel")
        bar = QHBoxLayout(bar_frame)
        bar.setContentsMargins(14, 10, 14, 10)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search anime title...")
        self._input.returnPressed.connect(self._on_search)
        search_btn = QPushButton("Search")
        search_btn.setObjectName("PrimaryButton")
        search_btn.clicked.connect(self._on_search)
        bar.addWidget(self._input, stretch=1)
        bar.addWidget(search_btn)
        layout.addWidget(bar_frame)

        self._status = QLabel("Enter a title to search.")
        layout.addWidget(self._status)

        self._scroll = SmoothScrollArea()
        self._container = QWidget()
        self._flow = FlowLayout(self._container, margin=10, spacing=16)
        self._scroll.setWidget(self._container)
        layout.addWidget(self._scroll, stretch=1)

    def _on_search(self) -> None:
        query = self._input.text().strip()
        if query:
            self.search_requested.emit(query)

    def set_results(self, label: str, items: list[AnimeSummary]) -> None:
        while self._flow.count():
            it = self._flow.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()
        for item in items:
            card = AnimeCard(item, self._poster_loader, self._container)
            card.clicked.connect(self.anime_selected.emit)
            self._flow.addWidget(card)
        self._status.setText(f"{label}: {len(items)} results")
