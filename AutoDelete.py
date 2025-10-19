"""AutoDelete.py

A simple Tkinter-based utility that simulates pressing the delete key on a
block of text. Paste or type text into the editor, click *Start* to begin
removing characters from the current cursor position, adjust the speed
slider to control how quickly characters disappear, and choose a font that
feels comfortable to work with.

The application also remembers its previous state—text contents, cursor
position, deletion speed, and window size—so that the next time it launches it
looks and feels just like it did when you last closed it.
"""

from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont


STATE_FILE = Path(__file__).with_suffix(".state.json")


class AutoDeleteApp:
    """GUI application that incrementally deletes text from a text widget."""

    MIN_SPEED = 1.0
    MAX_SPEED = 30.0

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Auto Delete")
        self.root.geometry("640x400")

        self._deleting = False

        base_font = tkfont.nametofont("TkTextFont")
        self.text_font = tkfont.Font(
            root=self.root,
            **base_font.actual(),
        )
        self.font_var = tk.StringVar(value=self.text_font.cget("family"))

        self._build_widgets()
        self._load_state()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_widgets(self) -> None:
        """Create and lay out widgets for the application."""
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        instructions = (
            "Paste or type text into the box below. Position the cursor where you "
            "would like deletion to start, then press Start. Adjust the speed "
            "slider at any time to change how quickly characters are removed, "
            "and choose a font that feels comfortable to work with."
        )
        instruction_label = ttk.Label(
            main_frame,
            text=instructions,
            wraplength=600,
            justify=tk.LEFT,
        )
        instruction_label.pack(fill=tk.X, pady=(0, 8))

        self.text = tk.Text(
            main_frame,
            wrap=tk.WORD,
            undo=True,
            font=self.text_font,
        )
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

        font_frame = ttk.Frame(controls_frame)
        font_frame.pack(side=tk.LEFT, padx=(12, 0))

        font_label = ttk.Label(font_frame, text="Font:")
        font_label.pack(side=tk.LEFT)

        self.font_combo = ttk.Combobox(
            font_frame,
            textvariable=self.font_var,
            values=self._available_font_families(),
            state="readonly",
            width=20,
        )
        self.font_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.font_combo.bind("<<ComboboxSelected>>", self._on_font_change)

        speed_frame = ttk.Frame(controls_frame)
        speed_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        speed_label = ttk.Label(speed_frame, text="Speed (characters/sec):")
        speed_label.pack(anchor=tk.W)

        self.speed_var = tk.DoubleVar(value=5.0)
        self.speed_scale = ttk.Scale(
            speed_frame,
            from_=self.MIN_SPEED,
            to=self.MAX_SPEED,
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

    def on_close(self) -> None:
        """Persist state and close the application."""
        self.stop_deleting()
        self._save_state()
        self.root.destroy()

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

    def _available_font_families(self) -> tuple[str, ...]:
        """Return a tuple of available font family names."""
        families = sorted({family for family in tkfont.families(self.root) if family})
        current_family = self.text_font.cget("family")
        if current_family:
            try:
                families.remove(current_family)
            except ValueError:
                pass
            families.insert(0, current_family)
        return tuple(families)

    def _on_font_change(self, _event: tk.Event) -> None:
        """Update the text widget font when the user selects a new family."""
        self._set_font_family(self.font_var.get())

    def _set_font_family(self, family: str) -> None:
        """Configure the editor font family and keep the selector in sync."""
        if not family:
            return

        try:
            self.text_font.config(family=family)
        except tk.TclError:
            return

        normalized_family = self.text_font.cget("family")
        if normalized_family != self.font_var.get():
            self.font_var.set(normalized_family)

        current_values = list(self.font_combo["values"])
        if normalized_family not in current_values:
            current_values.insert(0, normalized_family)
            self.font_combo["values"] = tuple(current_values)

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

    def _load_state(self) -> None:
        """Load saved editor state from disk if available."""
        if not STATE_FILE.exists():
            return

        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        content = data.get("content")
        if isinstance(content, str):
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)

        speed = data.get("speed")
        if isinstance(speed, (int, float)):
            clamped_speed = max(self.MIN_SPEED, min(self.MAX_SPEED, float(speed)))
            self.speed_var.set(clamped_speed)
            self._update_speed_display(str(clamped_speed))

        font_family = data.get("font_family")
        if isinstance(font_family, str):
            self._set_font_family(font_family)

        geometry = data.get("geometry")
        if isinstance(geometry, str):
            self.root.geometry(geometry)

        cursor_index = data.get("cursor")
        if isinstance(cursor_index, str):
            try:
                self.text.mark_set(tk.INSERT, cursor_index)
                self.text.see(tk.INSERT)
            except tk.TclError:
                pass

        if any(
            key in data
            for key in ("content", "speed", "geometry", "cursor")
        ):
            self.status_var.set("Restored previous session")

    def _save_state(self) -> None:
        """Persist the current editor state to disk."""
        state = {
            "content": self.text.get("1.0", tk.END),
            "cursor": self.text.index(tk.INSERT),
            "speed": self.speed_var.get(),
            "geometry": self.root.winfo_geometry(),
            "font_family": self.text_font.cget("family"),
        }

        try:
            STATE_FILE.write_text(
                json.dumps(state, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass


def main() -> None:
    """Entry point for launching the Auto Delete GUI."""
    root = tk.Tk()
    app = AutoDeleteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
