"""Dialog to add or update an episode stream entry in streams.json."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class AddStreamDialog(QDialog):
    """Collects episode number, stream URL, headers, and subtitle URL."""

    def __init__(self, anime_title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add / Update Stream — {anime_title}")
        self.resize(500, 310)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Target Anime: {anime_title}"))

        form = QFormLayout()
        self._ep_num = QLineEdit("1")
        self._ep_title = QLineEdit()
        self._ep_title.setPlaceholderText("Optional episode title")
        self._stream_url = QLineEdit()
        self._stream_url.setPlaceholderText("https://.../master.m3u8 or .mp4")
        self._referer = QLineEdit()
        self._referer.setPlaceholderText("Optional Referer header")
        self._user_agent = QLineEdit()
        self._user_agent.setPlaceholderText("Optional User-Agent header")
        self._sub_url = QLineEdit()
        self._sub_url.setPlaceholderText("Optional subtitle URL (.vtt / .srt)")

        form.addRow("Episode # *", self._ep_num)
        form.addRow("Episode Title", self._ep_title)
        form.addRow("Stream URL *", self._stream_url)
        form.addRow("Referer", self._referer)
        form.addRow("User-Agent", self._user_agent)
        form.addRow("Subtitle URL (en)", self._sub_url)
        layout.addLayout(form)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save & Open Episodes")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _on_save(self) -> None:
        if not self._ep_num.text().strip() or not self._stream_url.text().strip():
            QMessageBox.warning(
                self,
                "Missing Fields",
                "Episode number and Stream URL are required.",
            )
            return
        self.accept()

    def values(self) -> dict[str, str]:
        return {
            "episode_number": self._ep_num.text().strip(),
            "episode_title": self._ep_title.text().strip(),
            "stream_url": self._stream_url.text().strip(),
            "referer": self._referer.text().strip(),
            "user_agent": self._user_agent.text().strip(),
            "subtitle_url": self._sub_url.text().strip(),
        }
