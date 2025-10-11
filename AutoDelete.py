"""AutoDelete.py

A simple Tkinter-based utility that simulates pressing the delete key on a
block of text. Paste or type text into the editor, click *Start* to begin
removing characters from the current cursor position, and adjust the speed
slider to control how quickly characters disappear.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class AutoDeleteApp:
    """GUI application that incrementally deletes text from a text widget."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Auto Delete")
        self.root.geometry("640x400")

        self._deleting = False

        self._build_widgets()

    def _build_widgets(self) -> None:
        """Create and lay out widgets for the application."""
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        instructions = (
            "Paste or type text into the box below. Position the cursor where you "
            "would like deletion to start, then press Start. Adjust the speed "
            "slider at any time to change how quickly characters are removed."
        )
        instruction_label = ttk.Label(
            main_frame,
            text=instructions,
            wraplength=600,
            justify=tk.LEFT,
        )
        instruction_label.pack(fill=tk.X, pady=(0, 8))

        self.text = tk.Text(main_frame, wrap=tk.WORD, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True)

        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=(12, 0))

        buttons_frame = ttk.Frame(controls_frame)
        buttons_frame.pack(side=tk.LEFT)

        self.start_button = ttk.Button(
            buttons_frame,
            text="Start",
            command=self.start_deleting,
        )
        self.start_button.pack(side=tk.LEFT)

        self.stop_button = ttk.Button(
            buttons_frame,
            text="Stop",
            command=self.stop_deleting,
            state=tk.DISABLED,
        )
        self.stop_button.pack(side=tk.LEFT, padx=(8, 0))

        speed_frame = ttk.Frame(controls_frame)
        speed_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        speed_label = ttk.Label(speed_frame, text="Speed (characters/sec):")
        speed_label.pack(anchor=tk.W)

        self.speed_var = tk.DoubleVar(value=5.0)
        self.speed_scale = ttk.Scale(
            speed_frame,
            from_=1.0,
            to=30.0,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            command=self._update_speed_display,
        )
        self.speed_scale.pack(fill=tk.X, padx=(12, 0))

        self.speed_display = ttk.Label(
            speed_frame,
            text=self._format_speed_value(self.speed_var.get()),
        )
        self.speed_display.pack(anchor=tk.E, pady=(4, 0))

        self.status_var = tk.StringVar(value="Idle")
        status_label = ttk.Label(controls_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, padx=(12, 0))

    def start_deleting(self) -> None:
        """Begin deleting characters incrementally from the text widget."""
        if self._deleting:
            return

        self._deleting = True
        self.status_var.set("Deleting…")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.text.focus_set()
        self._schedule_next_delete()

    def stop_deleting(self) -> None:
        """Stop deleting characters."""
        if not self._deleting:
            return

        self._deleting = False
        self.status_var.set("Stopped")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def _schedule_next_delete(self) -> None:
        """Schedule the next deletion based on the configured speed."""
        if not self._deleting:
            return

        interval = max(1, int(1000 / max(0.1, self.speed_var.get())))
        self.root.after(interval, self._delete_one_character)

    def _format_speed_value(self, value: float) -> str:
        """Return a human-friendly representation of the speed setting."""
        return f"{value:.1f} chars/sec"

    def _update_speed_display(self, _value: str) -> None:
        """Update the speed readout label when the user adjusts the slider."""
        self.speed_display.config(
            text=self._format_speed_value(self.speed_var.get())
        )

    def _delete_one_character(self) -> None:
        """Remove a single character at the insertion cursor."""
        if not self._deleting:
            return

        insert_index = self.text.index(tk.INSERT)
        next_index = self.text.index(f"{insert_index} +1c")
        if insert_index == self.text.index(tk.END):
            self.stop_deleting()
            self.status_var.set("Finished")
            return

        char_to_delete = self.text.get(insert_index, next_index)
        if char_to_delete:
            self.text.delete(insert_index, next_index)
            self.status_var.set(
                f"Deleting… ({len(self.text.get('1.0', tk.END)) - 1} chars remaining)"
            )
            self._schedule_next_delete()
        else:
            # No more characters to delete; stop the process.
            self.stop_deleting()
            self.status_var.set("Finished")


def main() -> None:
    """Entry point for launching the Auto Delete GUI."""
    root = tk.Tk()
    app = AutoDeleteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
