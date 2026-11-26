#!/usr/bin/env python3
"""Generate a multi-size glassmorphism Windows .ico (assets/anilab.ico) using PySide6."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)

SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)


def render_icon_png(size: int) -> bytes:
    """Render a crisp frosted-glass rounded badge with a gradient play + waveform emblem."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    s = float(size)
    pad = s * 0.06
    rect = QRectF(pad, pad, s - 2 * pad, s - 2 * pad)
    radius = s * 0.23

    # Clip to rounded squircle badge
    badge_path = QPainterPath()
    badge_path.addRoundedRect(rect, radius, radius)
    p.setClipPath(badge_path)

    # Deep-space base gradient
    base_grad = QLinearGradient(0, 0, s, s)
    base_grad.setColorAt(0.0, QColor("#121528"))
    base_grad.setColorAt(0.55, QColor("#0d101e"))
    base_grad.setColorAt(1.0, QColor("#1a1333"))
    p.fillRect(rect, base_grad)

    # Ambient violet & cyan radial glows inside the glass
    g1 = QRadialGradient(s * 0.25, s * 0.22, s * 0.72)
    g1.setColorAt(0.0, QColor(148, 108, 255, 130))
    g1.setColorAt(0.6, QColor(90, 56, 195, 45))
    g1.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(rect, g1)

    g2 = QRadialGradient(s * 0.82, s * 0.84, s * 0.65)
    g2.setColorAt(0.0, QColor(56, 189, 248, 95))
    g2.setColorAt(0.65, QColor(30, 100, 175, 25))
    g2.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.fillRect(rect, g2)

    # Top frosted specular sheen
    sheen_grad = QLinearGradient(0, pad, 0, s * 0.52)
    sheen_grad.setColorAt(0.0, QColor(255, 255, 255, 48))
    sheen_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(pad, pad, rect.width(), rect.height() * 0.48), sheen_grad)

    # Play triangle emblem (slightly right-shifted for optical balance)
    tri_path = QPainterPath()
    left_x = s * 0.36
    right_x = s * 0.73
    top_y = s * 0.28
    bot_y = s * 0.72
    mid_y = s * 0.50
    tri_path.moveTo(QPointF(left_x, top_y))
    tri_path.lineTo(QPointF(right_x, mid_y))
    tri_path.lineTo(QPointF(left_x, bot_y))
    tri_path.closeSubpath()

    tri_grad = QLinearGradient(left_x, top_y, right_x, bot_y)
    tri_grad.setColorAt(0.0, QColor("#e9d5ff"))
    tri_grad.setColorAt(0.5, QColor("#a882ff"))
    tri_grad.setColorAt(1.0, QColor("#38bdf8"))
    p.fillPath(tri_path, tri_grad)

    # Subtle stylized waveform / accent bar on the left of the play mark
    if size >= 24:
        bar_w = max(1.5, s * 0.055)
        bar_x = s * 0.24
        bar_h = s * 0.28
        bar_rect = QRectF(bar_x, (s - bar_h) / 2.0, bar_w, bar_h)
        bar_grad = QLinearGradient(bar_rect.topLeft(), bar_rect.bottomLeft())
        bar_grad.setColorAt(0.0, QColor("#c4b5fd"))
        bar_grad.setColorAt(1.0, QColor("#38bdf8"))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bar_grad)
        p.drawRoundedRect(bar_rect, bar_w / 2.0, bar_w / 2.0)

    # Crisp 1px/scaled specular border around the glass badge
    p.setClipping(False)
    border_w = max(1.0, s * 0.028)
    border_grad = QLinearGradient(0, 0, s, s)
    border_grad.setColorAt(0.0, QColor(255, 255, 255, 165))
    border_grad.setColorAt(0.5, QColor(168, 130, 255, 120))
    border_grad.setColorAt(1.0, QColor(56, 189, 248, 110))
    p.setPen(QPen(border_grad, border_w))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(
        rect.adjusted(border_w / 2, border_w / 2, -border_w / 2, -border_w / 2),
        radius,
        radius,
    )
    p.end()

    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def write_ico(out_path: Path, sizes: tuple[int, ...] = SIZES) -> None:
    """Pack multiple PNG-encoded icon frames into a standard Windows .ico file."""
    frames = [(sz, render_icon_png(sz)) for sz in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries = bytearray()
    payload = bytearray()

    for sz, png_bytes in frames:
        dim = 0 if sz >= 256 else sz
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                dim,
                dim,
                0,
                0,
                1,
                32,
                len(png_bytes),
                offset,
            )
        )
        payload.extend(png_bytes)
        offset += len(png_bytes)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(bytes(header) + bytes(entries) + bytes(payload))


def main() -> int:
    _ = QGuiApplication.instance() or QGuiApplication(sys.argv)
    root = Path(__file__).resolve().parents[1]
    out = root / "assets" / "anilab.ico"
    write_ico(out)
    print(f"Generated {out} ({out.stat().st_size} bytes, sizes={list(SIZES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
