"""PySide6 application that deletes text incrementally like holding Delete."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QTimer, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QComboBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)

SPI_GETKEYBOARDSPEED = 0x000A
SPI_GETKEYBOARDDELAY = 0x0016
STATE_FILENAME = "last_session.txt"


def get_keyboard_repeat_settings() -> tuple[int, int]:
    if sys.platform != "win32":
        return 16, 1
    speed = ctypes.c_uint()
    delay = ctypes.c_uint()
    user32 = ctypes.windll.user32
    speed_ok = user32.SystemParametersInfoW(
        SPI_GETKEYBOARDSPEED, 0, ctypes.byref(speed), 0
    )
    delay_ok = user32.SystemParametersInfoW(
        SPI_GETKEYBOARDDELAY, 0, ctypes.byref(delay), 0
    )
    speed_value = int(speed.value) if speed_ok else 16
    delay_value = int(delay.value) if delay_ok else 1
    return max(0, min(speed_value, 31)), max(0, min(delay_value, 3))


def speed_notch_to_cps(notch: int) -> float:
    min_cps = 2.5
    max_cps = 30.0
    capped = max(0, min(notch, 31))
    return min_cps + (max_cps - min_cps) * (capped / 31)


def delay_notch_to_ms(delay_notch: int) -> int:
    capped = max(0, min(delay_notch, 3))
    return 250 * (capped + 1)


def get_state_path() -> Path:
    base_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / STATE_FILENAME


class DeleteController:
    """Handle incremental deletion without blocking the UI."""

    def __init__(self, editor: QPlainTextEdit, update_status) -> None:
        self.editor = editor
        self.update_status = update_status
        self.timer = QTimer()
        self.timer.setInterval(20)
        self.timer.timeout.connect(self._on_timeout)
        self.delay_timer = QTimer()
        self.delay_timer.setSingleShot(True)
        self.delay_timer.timeout.connect(self._start_repeating)
        self.running = False
        self.speed_cps = 10.0
        self._char_accumulator = 0.0

    def start(self, delay_ms: int) -> None:
        if self.running:
            return
        self.running = True
        self._char_accumulator = 0.0
        self.update_status("Deleting from cursor position...")
        self.delay_timer.start(max(0, delay_ms))

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.delay_timer.stop()
        self.timer.stop()
        self.update_status("Paused.")

    def set_speed(self, cps: float) -> None:
        self.speed_cps = max(0.1, float(cps))

    def _start_repeating(self) -> None:
        if self.running:
            self.timer.start()

    def _on_timeout(self) -> None:
        if not self.running:
            return
        document = self.editor.document()
        max_position = max(0, document.characterCount() - 1)
        if max_position == 0:
            self.stop()
            self.update_status("Nothing left to delete.")
            return

        per_tick = self.speed_cps * self.timer.interval() / 1000
        self._char_accumulator += per_tick
        batch = max(0, int(self._char_accumulator))
        if batch == 0:
            return
        self._char_accumulator -= batch
        cursor = self.editor.textCursor()
        if not cursor.hasSelection() and cursor.position() >= max_position:
            self.stop()
            self.update_status("Cursor is past the end of the text.")
            return
        cursor.beginEditBlock()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            for _ in range(batch):
                if cursor.position() >= max_position:
                    break
                cursor.deleteChar()
        cursor.endEditBlock()
        self.editor.setTextCursor(cursor)


class TextDeleterWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Incremental Text Deleter")
        self.resize(1000, 700)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText("")
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.editor.setFont(QFont("Courier New", 10))

        self.status_label = QLabel("Paste text, place cursor, then Start.")
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.counts_label = QLabel("Lines: 0  |  Characters: 0")
        self.counts_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.repeat_rate, self.repeat_delay = get_keyboard_repeat_settings()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, 31)
        self.speed_slider.setValue(self.repeat_rate)
        self.speed_slider.setTickInterval(1)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)

        self.theme_button = QPushButton("Dark mode")
        self.dark_mode = False

        self.font_selector = QComboBox()
        self.font_selector.addItems(["Arial", "Courier New", "Consolas"])
        self.font_selector.setCurrentText("Courier New")

        self.size_selector = QComboBox()
        self.size_selector.addItems(["10", "12", "14"])
        self.size_selector.setCurrentText("10")

        self.controller = DeleteController(self.editor, self._set_status)
        self.controller.set_speed(speed_notch_to_cps(self.speed_slider.value()))

        self._build_layout()
        self._connect_signals()
        self._apply_theme()
        self._update_counts()
        self._load_saved_text()

    def _build_layout(self) -> None:
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.start_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel("Repeat rate:"))
        toolbar.addWidget(self.speed_slider, 1)
        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel("Font:"))
        toolbar.addWidget(self.font_selector)
        toolbar.addWidget(QLabel("Size:"))
        toolbar.addWidget(self.size_selector)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.theme_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self.editor, 1)
        status_layout = QHBoxLayout()
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.counts_label)
        main_layout.addLayout(status_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start)
        self.stop_button.clicked.connect(self._on_stop)
        self.speed_slider.valueChanged.connect(self._on_repeat_rate_changed)
        self.theme_button.clicked.connect(self._toggle_theme)
        self.editor.textChanged.connect(self._update_counts)
        self.font_selector.currentTextChanged.connect(self._apply_editor_font)
        self.size_selector.currentTextChanged.connect(self._apply_editor_font)
        self._apply_editor_font()

    def _on_start(self) -> None:
        delay_ms = delay_notch_to_ms(self.repeat_delay)
        self.controller.start(delay_ms)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def _on_stop(self) -> None:
        self.controller.stop()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        if not self.controller.running:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def _on_repeat_rate_changed(self, value: int) -> None:
        self.repeat_rate = value
        self.controller.set_speed(speed_notch_to_cps(value))

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()

    def _apply_editor_font(self) -> None:
        family = self.font_selector.currentText()
        size = int(self.size_selector.currentText())
        self.editor.setFont(QFont(family, size))

    def _update_counts(self) -> None:
        lines = self.editor.blockCount()
        chars = max(0, self.editor.document().characterCount() - 1)
        self.counts_label.setText(f"Lines: {lines}  |  Characters: {chars}")

    def _load_saved_text(self) -> None:
        path = get_state_path()
        if path.exists():
            self.editor.setPlainText(path.read_text(encoding="utf-8"))
            self._update_counts()

    def _save_text(self) -> None:
        path = get_state_path()
        path.write_text(self.editor.toPlainText(), encoding="utf-8")

    def closeEvent(self, event) -> None:
        self._save_text()
        super().closeEvent(event)

    def _apply_theme(self) -> None:
        palette = QPalette()
        if self.dark_mode:
            palette.setColor(QPalette.Window, Qt.black)
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, Qt.black)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, Qt.darkGray)
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.Highlight, Qt.gray)
            self.theme_button.setText("Light mode")
        else:
            palette = QApplication.style().standardPalette()
            self.theme_button.setText("Dark mode")
        QApplication.instance().setPalette(palette)


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = TextDeleterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
