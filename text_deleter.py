"""PySide6 application that deletes text incrementally like holding Delete."""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QPlainTextEdit,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class DeleteController:
    """Handle incremental deletion without blocking the UI."""

    def __init__(self, editor: QPlainTextEdit, update_status) -> None:
        self.editor = editor
        self.update_status = update_status
        self.timer = QTimer()
        self.timer.setInterval(30)
        self.timer.timeout.connect(self._on_timeout)
        self.running = False
        self.speed_cps = 120

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.update_status("Deleting from cursor position...")
        self.timer.start()

    def stop(self) -> None:
        if not self.running:
            return
        self.running = False
        self.timer.stop()
        self.update_status("Paused.")

    def set_speed(self, cps: int) -> None:
        self.speed_cps = max(1, cps)

    def _on_timeout(self) -> None:
        if not self.running:
            return
        document = self.editor.document()
        max_position = max(0, document.characterCount() - 1)
        if max_position == 0:
            self.stop()
            self.update_status("Nothing left to delete.")
            return

        batch = max(1, int(self.speed_cps * self.timer.interval() / 1000))
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

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)

        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 800)
        self.speed_slider.setValue(120)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 800)
        self.speed_spin.setValue(120)

        self.theme_button = QPushButton("Dark mode")
        self.dark_mode = False

        self.controller = DeleteController(self.editor, self._set_status)
        self.controller.set_speed(self.speed_slider.value())

        self._build_layout()
        self._connect_signals()
        self._apply_theme()

    def _build_layout(self) -> None:
        toolbar = QHBoxLayout()
        toolbar.addWidget(self.start_button)
        toolbar.addWidget(self.stop_button)
        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel("Speed (chars/sec):"))
        toolbar.addWidget(self.speed_slider, 1)
        toolbar.addWidget(self.speed_spin)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.theme_button)

        main_layout = QVBoxLayout()
        main_layout.addLayout(toolbar)
        main_layout.addWidget(self.editor, 1)
        main_layout.addWidget(self.status_label)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._on_start)
        self.stop_button.clicked.connect(self._on_stop)
        self.speed_slider.valueChanged.connect(self.speed_spin.setValue)
        self.speed_spin.valueChanged.connect(self.speed_slider.setValue)
        self.speed_slider.valueChanged.connect(self.controller.set_speed)
        self.theme_button.clicked.connect(self._toggle_theme)

    def _on_start(self) -> None:
        self.controller.start()
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

    def _toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self._apply_theme()

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
