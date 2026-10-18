"""Screen S3: Accessible Communication Board for MORPH 2.0."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class PhraseTile(QPushButton):
    """Accessible phrase tile widget with high-contrast active and selected states."""

    def __init__(self, phrase_id: str, text: str, parent=None):
        super().__init__(text, parent)
        self.phrase_id = phrase_id
        self.phrase_text = text
        self.setAccessibleName(f"Phrase Tile: {text}")
        self.setAccessibleDescription(f"Communication phrase: {text}. Select to speak.")
        self.setMinimumSize(180, 100)
        self.setCheckable(False)
        self._is_highlighted = False
        self._update_style()

    def set_highlighted(self, highlighted: bool) -> None:
        self._is_highlighted = highlighted
        self._update_style()

    def flash_spoken(self) -> None:
        """Visual acknowledgment when phrase is spoken."""
        self.setStyleSheet(
            "background-color: #059669; color: #FFFFFF; font-size: 20px; font-weight: 800; "
            "border: 4px solid #34D399; border-radius: 12px;"
        )
        QTimer.singleShot(400, self._update_style)

    def _update_style(self) -> None:
        if self._is_highlighted:
            self.setStyleSheet(
                "background-color: #1E293B; color: #38BDF8; font-size: 19px; font-weight: 700; "
                "border: 4px solid #38BDF8; border-radius: 12px;"
            )
        else:
            self.setStyleSheet(
                "background-color: #0F172A; color: #E2E8F0; font-size: 18px; font-weight: 600; "
                "border: 2px solid #334155; border-radius: 12px;"
            )


class BoardView(QWidget):
    """S3 Communication Board: Grid of accessible phrase tiles with offline TTS."""

    phrase_spoken = Signal(str)  # phrase text
    pause_toggled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAccessibleName("Communication Board Screen")
        self.setAccessibleDescription(
            "Screen containing communication phrase tiles that can be navigated and spoken using facial gestures or keyboard."
        )

        self.current_index = 0
        self.tiles: list[PhraseTile] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Communication Board")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #38BDF8;")
        subtitle = QLabel(
            "Navigate tiles and speak phrases using trained gestures or keyboard (Tab/Arrows/Enter)"
        )
        subtitle.setStyleSheet("color: #94A3B8; font-size: 14px;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.btn_pause = QPushButton("⏸ Quick Pause (Space)")
        self.btn_pause.setAccessibleName("Quick Pause Toggle")
        self.btn_pause.clicked.connect(self.pause_toggled.emit)
        header.addWidget(self.btn_pause)
        layout.addLayout(header)

        # Last Spoken Banner
        self.spoken_banner = QLabel("Last Spoken: None")
        self.spoken_banner.setStyleSheet(
            "background-color: #1E293B; color: #38BDF8; font-size: 16px; font-weight: bold; "
            "padding: 12px 20px; border: 1px solid #334155; border-radius: 8px;"
        )
        self.spoken_banner.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.spoken_banner)

        # Tiles Grid
        grid_frame = QFrame()
        grid_layout = QGridLayout(grid_frame)
        grid_layout.setSpacing(16)

        phrases = [
            ("p1", "Yes, please"),
            ("p2", "No, thank you"),
            ("p3", "I need water"),
            ("p4", "I am in pain"),
            ("p5", "Please adjust my position"),
            ("p6", "I need assistance"),
            ("p7", "I am tired / want to rest"),
            ("p8", "Thank you very much"),
            ("p9", "Everything is okay"),
        ]

        cols = 3
        for i, (p_id, text) in enumerate(phrases):
            tile = PhraseTile(p_id, text)
            row = i // cols
            col = i % cols
            tile.clicked.connect(lambda _, idx=i: self.select_and_speak_index(idx))
            grid_layout.addWidget(tile, row, col)
            self.tiles.append(tile)

        layout.addWidget(grid_frame)
        layout.addStretch()

        # Update initial focus
        self._update_focus()

    def navigate_next(self) -> None:
        """Move focus to next tile."""
        if not self.tiles:
            return
        self.current_index = (self.current_index + 1) % len(self.tiles)
        self._update_focus()

    def navigate_previous(self) -> None:
        """Move focus to previous tile."""
        if not self.tiles:
            return
        self.current_index = (self.current_index - 1 + len(self.tiles)) % len(self.tiles)
        self._update_focus()

    def select_current(self) -> str:
        """Speak the currently focused tile."""
        return self.select_and_speak_index(self.current_index)

    def select_and_speak_index(self, index: int) -> str:
        if 0 <= index < len(self.tiles):
            self.current_index = index
            self._update_focus()
            tile = self.tiles[index]
            tile.flash_spoken()
            text = tile.phrase_text
            self.spoken_banner.setText(f'Last Spoken: "{text}"')
            self.phrase_spoken.emit(text)
            return text
        return ""

    def _update_focus(self) -> None:
        for i, tile in enumerate(self.tiles):
            tile.set_highlighted(i == self.current_index)
            if i == self.current_index:
                tile.setFocus()
