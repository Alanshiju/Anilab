"""Shared glassmorphism styling, smooth scrolling, image loader, and animated AnimeCard."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from anilab_desktop.models.catalog import AnimeSummary

APP_STYLESHEET = """
QMainWindow, QDialog {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #070b14,
        stop: 0.45 #0f172a,
        stop: 1 #131129
    );
    color: #e5e7eb;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e5e7eb;
    background: transparent;
}

QFrame#GlassNav {
    background-color: rgba(17, 24, 39, 0.68);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 16px;
}

QFrame#GlassPanel {
    background-color: rgba(20, 27, 45, 0.66);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 16px;
}

QFrame#AnimeCard {
    background-color: rgba(24, 33, 56, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
}

QFrame#AnimeCard[hovered="true"] {
    background-color: rgba(36, 48, 82, 0.86);
    border: 1px solid rgba(167, 139, 250, 0.78);
}

QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    background-color: rgba(15, 23, 42, 0.52);
    padding: 8px;
}

QTabBar::tab {
    background-color: rgba(255, 255, 255, 0.06);
    color: #9ca3af;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 10px;
    padding: 7px 16px;
    margin-right: 6px;
    margin-bottom: 6px;
    font-weight: 600;
}

QTabBar::tab:selected {
    background-color: rgba(124, 58, 237, 0.38);
    color: #ffffff;
    border: 1px solid rgba(167, 139, 250, 0.65);
}

QTabBar::tab:hover:!selected {
    background-color: rgba(255, 255, 255, 0.11);
    color: #f3f4f6;
}

QPushButton {
    background-color: rgba(255, 255, 255, 0.08);
    color: #f9fafb;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    padding: 7px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(124, 58, 237, 0.40);
    border: 1px solid rgba(167, 139, 250, 0.65);
}

QPushButton:pressed {
    background-color: rgba(109, 40, 217, 0.68);
}

QPushButton#PrimaryButton {
    background-color: rgba(124, 58, 237, 0.78);
    border: 1px solid rgba(196, 181, 253, 0.58);
}

QPushButton#PrimaryButton:hover {
    background-color: rgba(139, 92, 246, 0.94);
}

QPushButton#NavButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 7px 14px;
    color: #9ca3af;
}

QPushButton#NavButton[active="true"] {
    background-color: rgba(124, 58, 237, 0.36);
    border: 1px solid rgba(167, 139, 250, 0.58);
    color: #ffffff;
}

QPushButton#NavButton:hover:!active {
    background-color: rgba(255, 255, 255, 0.08);
    color: #f3f4f6;
}

QComboBox {
    background-color: rgba(15, 23, 42, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 10px;
    padding: 6px 12px;
    color: #f3f4f6;
    font-weight: 600;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    border: 1px solid rgba(255, 255, 255, 0.16);
    selection-background-color: rgba(124, 58, 237, 0.55);
    color: #f9fafb;
}

QLineEdit, QTextEdit, QListWidget {
    background-color: rgba(15, 23, 42, 0.74);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 12px;
    padding: 8px 12px;
    color: #f3f4f6;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid rgba(167, 139, 250, 0.72);
}

QListWidget::item {
    padding: 8px 10px;
    border-radius: 8px;
    margin: 2px 0px;
}

QListWidget::item:selected {
    background-color: rgba(124, 58, 237, 0.42);
    border: 1px solid rgba(167, 139, 250, 0.55);
}

QListWidget::item:hover:!selected {
    background-color: rgba(255, 255, 255, 0.07);
}

QLabel#Badge {
    background-color: rgba(255, 255, 255, 0.09);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 7px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #d1d5db;
}

QLabel#ScoreBadge {
    background-color: rgba(245, 158, 11, 0.22);
    border: 1px solid rgba(251, 191, 36, 0.45);
    border-radius: 7px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
    color: #fde68a;
}

QLabel#WatchedBadge {
    background-color: rgba(16, 185, 129, 0.20);
    border: 1px solid rgba(52, 211, 153, 0.45);
    border-radius: 7px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 700;
    color: #a7f3d0;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.18);
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(167, 139, 250, 0.58);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def apply_glass_shadow(
    widget: QWidget, *, blur: int = 24, alpha: int = 115
) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 6)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


class SmoothScrollArea(QScrollArea):
    """QScrollArea with QPropertyAnimation + OutCubic wheel scrolling."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._target_value = 0

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = int(-delta * 0.9)
        base = (
            self._target_value
            if self._anim.state() == QPropertyAnimation.State.Running
            else bar.value()
        )
        new_val = max(bar.minimum(), min(bar.maximum(), base + step))
        self._target_value = new_val
        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(new_val)
        self._anim.start()
        event.accept()


class FlowLayout(QLayout):
    """Responsive wrapping layout for AnimeCard grids."""

    def __init__(self, parent=None, margin: int = 8, spacing: int = 14) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0

        for item in self._items:
            sz = item.sizeHint()
            next_x = x + sz.width() + self._spacing
            if next_x - self._spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._spacing
                next_x = x + sz.width() + self._spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), sz))
            x = next_x
            line_height = max(line_height, sz.height())

        return y + line_height - rect.y() + m.bottom()


class PosterLoader:
    """Async QNetworkAccessManager image loader with in-memory QPixmap cache."""

    def __init__(self, parent=None) -> None:
        self._nam = QNetworkAccessManager(parent)
        self._cache: dict[str, QPixmap] = {}
        self._pending: dict[str, list[Callable[[QPixmap], None]]] = {}

    def load(self, url: str | None, callback: Callable[[QPixmap], None]) -> None:
        if not url:
            return
        if url in self._cache:
            callback(self._cache[url])
            return
        if url in self._pending:
            self._pending[url].append(callback)
            return

        self._pending[url] = [callback]
        req = QNetworkRequest(QUrl(url))
        reply = self._nam.get(req)
        reply.finished.connect(lambda r=reply, u=url: self._on_finished(r, u))

    def _on_finished(self, reply: QNetworkReply, url: str) -> None:
        callbacks = self._pending.pop(url, [])
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                pix = QPixmap()
                if pix.loadFromData(bytes(reply.readAll())):
                    self._cache[url] = pix
                    for cb in callbacks:
                        cb(pix)
        finally:
            reply.deleteLater()


def rounded_pixmap(pix: QPixmap, target_size: QSize, radius: int = 10) -> QPixmap:
    """Scale-crop pixmap to target_size with rounded corners."""
    scaled = pix.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - target_size.width()) // 2)
    y = max(0, (scaled.height() - target_size.height()) // 2)
    cropped = scaled.copy(x, y, target_size.width(), target_size.height())

    out = QPixmap(target_size)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, target_size.width(), target_size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return out


class AnimeCard(QFrame):
    """Animated glass anime card with poster artwork, badges, and hover glow."""

    clicked = Signal(int)

    CARD_W = 188
    CARD_H = 324
    POSTER_W = 166
    POSTER_H = 228

    def __init__(
        self,
        item: AnimeSummary,
        poster_loader: PosterLoader | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._anime_id = item.id
        self.setObjectName("AnimeCard")
        self.setProperty("hovered", False)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._shadow = apply_glass_shadow(self, blur=16, alpha=110)

        self._blur_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._blur_anim.setDuration(160)
        self._blur_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(7)

        self._poster = QLabel("Loading...")
        self._poster.setFixedSize(self.POSTER_W, self.POSTER_H)
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setStyleSheet(
            "background-color: rgba(255,255,255,0.05); "
            "border-radius: 12px; color: #6b7280; font-size: 11px;"
        )
        layout.addWidget(self._poster)

        title_lbl = QLabel(item.title)
        title_lbl.setWordWrap(True)
        title_lbl.setMaximumHeight(38)
        title_lbl.setStyleSheet("font-weight: 700; font-size: 12.5px; color: #f9fafb;")
        layout.addWidget(title_lbl)

        badges = QHBoxLayout()
        badges.setSpacing(4)
        if item.score:
            sb = QLabel(f"★ {item.score}")
            sb.setObjectName("ScoreBadge")
            badges.addWidget(sb)
        if item.type:
            tb = QLabel(item.type)
            tb.setObjectName("Badge")
            badges.addWidget(tb)
        if item.latestEpisode:
            eb = QLabel(f"Ep {item.latestEpisode}")
            eb.setObjectName("Badge")
            badges.addWidget(eb)
        badges.addStretch()
        layout.addLayout(badges)

        poster_url = item.posterUrl or item.largePosterUrl
        if poster_loader is not None and poster_url:
            poster_loader.load(poster_url, self._set_poster)

    def _set_poster(self, pix: QPixmap) -> None:
        self._poster.setText("")
        self._poster.setPixmap(
            rounded_pixmap(pix, QSize(self.POSTER_W, self.POSTER_H), radius=12)
        )

    def enterEvent(self, event) -> None:
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self._shadow.setColor(QColor(139, 92, 246, 155))
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._shadow.blurRadius())
        self._blur_anim.setEndValue(30)
        self._blur_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self._shadow.setColor(QColor(0, 0, 0, 110))
        self._blur_anim.stop()
        self._blur_anim.setStartValue(self._shadow.blurRadius())
        self._blur_anim.setEndValue(16)
        self._blur_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._anime_id)
        super().mousePressEvent(event)
