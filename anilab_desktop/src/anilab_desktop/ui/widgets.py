"""Apple-style glassmorphism styling, 60fps smooth scrolling, cached image loader, and AnimeCard."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QFrame,
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
QMainWindow {
    background: transparent;
    color: #f3f4f6;
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QDialog {
    background-color: #0b0e18;
    color: #f3f4f6;
    font-family: "Segoe UI Variable", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget {
    color: #f3f4f6;
    background: transparent;
}

QFrame#GlassNav {
    background-color: rgba(24, 26, 38, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
}

QFrame#GlassPanel {
    background-color: rgba(24, 26, 38, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
}

QFrame#SegmentedControl {
    background-color: rgba(12, 14, 22, 0.62);
    border: 1px solid rgba(255, 255, 255, 0.11);
    border-radius: 14px;
    padding: 3px;
}

QFrame#AnimeCard {
    background-color: rgba(24, 26, 38, 0.58);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
}

QFrame#AnimeCard[hovered="true"] {
    background-color: rgba(38, 42, 66, 0.78);
    border: 1px solid rgba(168, 130, 255, 0.55);
}

QPushButton {
    background-color: rgba(255, 255, 255, 0.08);
    color: #f9fafb;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 11px;
    padding: 7px 15px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: rgba(168, 130, 255, 0.28);
    border: 1px solid rgba(168, 130, 255, 0.55);
}

QPushButton:pressed {
    background-color: rgba(139, 92, 246, 0.55);
}

QPushButton#PrimaryButton {
    background-color: rgba(139, 92, 246, 0.85);
    border: 1px solid rgba(216, 180, 254, 0.58);
    color: #ffffff;
    font-weight: 700;
}

QPushButton#PrimaryButton:hover {
    background-color: rgba(154, 112, 255, 0.96);
    border: 1px solid rgba(233, 213, 255, 0.80);
}

QPushButton#NavButton {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 11px;
    padding: 6px 18px;
    color: #9ca3af;
    font-weight: 600;
}

QPushButton#NavButton[active="true"] {
    background-color: rgba(139, 92, 246, 0.42);
    border: 1px solid rgba(196, 181, 253, 0.52);
    color: #ffffff;
}

QPushButton#NavButton:hover:!active {
    background-color: rgba(255, 255, 255, 0.07);
    color: #f3f4f6;
}

QComboBox {
    background-color: rgba(18, 20, 32, 0.78);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 11px;
    padding: 6px 12px;
    color: #f3f4f6;
    font-weight: 600;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #121420;
    border: 1px solid rgba(255, 255, 255, 0.16);
    selection-background-color: rgba(139, 92, 246, 0.55);
    color: #f9fafb;
    outline: 0;
}

QLineEdit, QTextEdit, QListWidget {
    background-color: rgba(16, 18, 28, 0.72);
    border: 1px solid rgba(255, 255, 255, 0.13);
    border-radius: 13px;
    padding: 8px 12px;
    color: #f3f4f6;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid rgba(168, 130, 255, 0.65);
}

QListWidget::item {
    padding: 9px 12px;
    border-radius: 10px;
    margin: 2px 0px;
}

QListWidget::item:selected {
    background-color: rgba(139, 92, 246, 0.42);
    border: 1px solid rgba(196, 181, 253, 0.52);
}

QListWidget::item:hover:!selected {
    background-color: rgba(255, 255, 255, 0.07);
}

QLabel#Badge {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10.5px;
    font-weight: 600;
    color: #d1d5db;
}

QLabel#ScoreBadge {
    background-color: rgba(245, 158, 11, 0.20);
    border: 1px solid rgba(251, 191, 36, 0.42);
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10.5px;
    font-weight: 700;
    color: #fde68a;
}

QLabel#WatchedBadge {
    background-color: rgba(16, 185, 129, 0.20);
    border: 1px solid rgba(52, 211, 153, 0.45);
    border-radius: 8px;
    padding: 2px 7px;
    font-size: 10.5px;
    font-weight: 700;
    color: #a7f3d0;
}

QScrollArea {
    border: none;
    background: transparent;
}

QScrollBar:vertical {
    background: transparent;
    width: 7px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 0.18);
    border-radius: 3px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: rgba(168, 130, 255, 0.58);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


def get_app_icon() -> QIcon:
    """Load assets/anilab.ico from _MEIPASS (frozen) or repository root (dev)."""
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "assets" / "anilab.ico")
        candidates.append(Path(sys.executable).resolve().parent / "assets" / "anilab.ico")
    # Dev mode: src/anilab_desktop/ui/widgets.py -> anilab_desktop/assets/anilab.ico
    candidates.append(Path(__file__).resolve().parents[3] / "assets" / "anilab.ico")
    for path in candidates:
        if path.is_file():
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon
    return QIcon()


def apply_windows_dwm_style(widget: QWidget) -> None:
    """Apply Windows 11 DWM dark mode, acrylic backdrop, and rounded corners safely."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = int(widget.winId())
        if not hwnd:
            return
        dwmapi = ctypes.windll.dwmapi
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        dark = ctypes.c_int(1)
        dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(dark), ctypes.sizeof(dark))
        # DWMWA_WINDOW_CORNER_PREFERENCE = 33 (2 = DWMWCP_ROUND)
        corner = ctypes.c_int(2)
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(corner), ctypes.sizeof(corner))
        # DWMWA_SYSTEMBACKDROP_TYPE = 38 (3 = DWMSBT_TRANSIENTWINDOW / Acrylic)
        backdrop = ctypes.c_int(3)
        dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(backdrop), ctypes.sizeof(backdrop))
    except Exception:
        pass


def build_ambient_backdrop(size: QSize) -> QPixmap:
    """Render a deep-space radial/mesh gradient backdrop into a cached QPixmap."""
    w = max(1, size.width())
    h = max(1, size.height())
    pix = QPixmap(w, h)
    pix.fill(QColor("#070911"))

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Top-left soft violet/indigo ambient glow
    g1 = QRadialGradient(w * 0.16, h * 0.14, max(w, h) * 0.65)
    g1.setColorAt(0.0, QColor(99, 60, 195, 78))
    g1.setColorAt(0.55, QColor(45, 32, 110, 32))
    g1.setColorAt(1.0, QColor(7, 9, 17, 0))
    painter.fillRect(0, 0, w, h, g1)

    # Bottom-right deep cyan/indigo ambient glow
    g2 = QRadialGradient(w * 0.85, h * 0.84, max(w, h) * 0.60)
    g2.setColorAt(0.0, QColor(28, 100, 165, 62))
    g2.setColorAt(0.55, QColor(18, 45, 92, 26))
    g2.setColorAt(1.0, QColor(7, 9, 17, 0))
    painter.fillRect(0, 0, w, h, g2)

    # Subtle center-top specular wash
    g3 = QRadialGradient(w * 0.50, 0.0, max(w, h) * 0.45)
    g3.setColorAt(0.0, QColor(168, 130, 255, 28))
    g3.setColorAt(1.0, QColor(7, 9, 17, 0))
    painter.fillRect(0, 0, w, h, g3)

    painter.end()
    return pix


def apply_glass_shadow(
    widget: QWidget, *, blur: int = 24, alpha: int = 115
) -> None:
    """Kept for API compatibility; avoids expensive QGraphicsDropShadowEffect CPU repaints."""
    _ = (widget, blur, alpha)
    return None


class SmoothScrollArea(QScrollArea):
    """QScrollArea with 60fps OutCubic wheel interpolation and debounced resize relayout."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalScrollBar().setSingleStep(20)
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._target_value = 0

        self._relayout_timer = QTimer(self)
        self._relayout_timer.setSingleShot(True)
        self._relayout_timer.setInterval(20)
        self._relayout_timer.timeout.connect(self._flush_relayout)

    def _flush_relayout(self) -> None:
        w = self.widget()
        if w is not None and w.layout() is not None:
            w.layout().activate()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout_timer.start()

    def wheelEvent(self, event) -> None:
        bar = self.verticalScrollBar()
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return
        step = int(-delta * 0.95)
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
    """Responsive wrapping layout for AnimeCard grids with geometry caching."""

    def __init__(self, parent=None, margin: int = 8, spacing: int = 16) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self._last_rect = QRect()
        self._last_count = -1
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:
        self._items.append(item)
        self._last_count = -1

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int):
        if 0 <= index < len(self._items):
            self._last_count = -1
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
        if rect == self._last_rect and len(self._items) == self._last_count:
            return
        self._last_rect = QRect(rect)
        self._last_count = len(self._items)
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
    """Async QNetworkAccessManager image loader with raw + rounded QPixmap cache."""

    def __init__(self, parent=None) -> None:
        self._nam = QNetworkAccessManager(parent)
        self._cache: dict[str, QPixmap] = {}
        self._rounded_cache: dict[tuple[str, int, int, int], QPixmap] = {}
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

    def load_rounded(
        self,
        url: str | None,
        target_size: QSize,
        radius: int,
        callback: Callable[[QPixmap], None],
    ) -> None:
        if not url:
            return
        key = (url, target_size.width(), target_size.height(), radius)
        if key in self._rounded_cache:
            callback(self._rounded_cache[key])
            return

        def _on_raw(pix: QPixmap) -> None:
            rounded = self._rounded_cache.get(key)
            if rounded is None:
                rounded = rounded_pixmap(pix, target_size, radius=radius)
                self._rounded_cache[key] = rounded
            callback(rounded)

        self.load(url, _on_raw)

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


def rounded_pixmap(pix: QPixmap, target_size: QSize, radius: int = 12) -> QPixmap:
    """Scale-crop pixmap to target_size with anti-aliased rounded corners."""
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
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(0, 0, target_size.width(), target_size.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return out


def _elide_two_lines(text: str, font: QFont, max_width: int) -> str:
    """Wrap text cleanly into at most 2 lines with QFontMetrics.elidedText."""
    fm = QFontMetrics(font)
    clean = " ".join(text.split())
    if not clean:
        return ""
    if fm.horizontalAdvance(clean) <= max_width:
        return clean

    words = clean.split(" ")
    line1 = ""
    idx = 0
    for i, word in enumerate(words):
        cand = word if not line1 else f"{line1} {word}"
        if fm.horizontalAdvance(cand) <= max_width:
            line1 = cand
            idx = i + 1
        else:
            break

    if not line1:
        # Single long word without spaces
        first = fm.elidedText(clean, Qt.TextElideMode.ElideNone, max_width)
        rest = clean[len(first):].strip()
        if not rest:
            return first
        line2 = fm.elidedText(rest, Qt.TextElideMode.ElideRight, max_width)
        return f"{first}\n{line2}"

    remaining = " ".join(words[idx:]).strip()
    if not remaining:
        return line1
    line2 = fm.elidedText(remaining, Qt.TextElideMode.ElideRight, max_width)
    return f"{line1}\n{line2}"


class AnimeCard(QFrame):
    """60fps frosted-glass anime card with cached rounded poster, 2-line elided title, and pills."""

    clicked = Signal(int)

    CARD_W = 192
    CARD_H = 342
    POSTER_W = 170
    POSTER_H = 236

    def __init__(
        self,
        item: AnimeSummary,
        poster_loader: PosterLoader | None = None,
        parent=None,
        *,
        last_watched: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._anime_id = item.id
        self.setObjectName("AnimeCard")
        self.setProperty("hovered", False)
        self.setFixedSize(self.CARD_W, self.CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(7)

        self._poster = QLabel("Loading...")
        self._poster.setFixedSize(self.POSTER_W, self.POSTER_H)
        self._poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._poster.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.05); "
            "border-radius: 12px; color: #6b7280; font-size: 11px;"
        )
        layout.addWidget(self._poster)

        title_font = QFont(self.font())
        title_font.setPointSizeF(9.5)
        title_font.setWeight(QFont.Weight.Bold)
        elided_title = _elide_two_lines(item.title, title_font, self.POSTER_W - 2)
        title_lbl = QLabel(elided_title)
        title_lbl.setFont(title_font)
        title_lbl.setToolTip(item.title)
        title_lbl.setFixedHeight(38)
        title_lbl.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        title_lbl.setStyleSheet("color: #f9fafb; background: transparent;")
        layout.addWidget(title_lbl)

        badges = QHBoxLayout()
        badges.setSpacing(4)
        badges.setContentsMargins(0, 0, 0, 0)
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
        if last_watched:
            wb = QLabel(f"● {last_watched}")
            wb.setObjectName("WatchedBadge")
            badges.addWidget(wb)
        badges.addStretch()
        layout.addLayout(badges)

        poster_url = item.posterUrl or item.largePosterUrl
        if poster_loader is not None and poster_url:
            poster_loader.load_rounded(
                poster_url,
                QSize(self.POSTER_W, self.POSTER_H),
                12,
                self._set_poster,
            )

    def _set_poster(self, pix: QPixmap) -> None:
        self._poster.setText("")
        self._poster.setPixmap(pix)

    def enterEvent(self, event) -> None:
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._anime_id)
        super().mousePressEvent(event)
