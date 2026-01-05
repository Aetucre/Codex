"""Simple Tkinter application that deletes text incrementally like a delete key."""

import tkinter as tk
from tkinter import ttk


class TextDeleterApp:
    """GUI application that deletes text from the insertion point at a configurable speed."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Incremental Text Deleter")

        self.deleting = False
        self.after_id: str | None = None

        self._build_widgets()

    def _build_widgets(self) -> None:
        """Create and layout all widgets for the UI."""
        main_frame = ttk.Frame(self.root, padding="16")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        instructions = (
            "Paste text below, place the cursor where deletion should begin, and click "
            "Start. The text will be deleted a character at a time. Adjust the speed "
            "slider at any time to change how fast characters are removed."
        )
        ttk.Label(main_frame, text=instructions, wraplength=420, justify="left").grid(
            row=0, column=0, columnspan=3, sticky="we", pady=(0, 12)
        )

        self.text = tk.Text(main_frame, width=60, height=18, wrap="word")
        self.text.grid(row=1, column=0, columnspan=3, sticky="nsew")

        controls_frame = ttk.Frame(main_frame)
        controls_frame.grid(row=2, column=0, columnspan=3, sticky="we", pady=(12, 0))
        controls_frame.columnconfigure(3, weight=1)

        self.start_button = ttk.Button(
            controls_frame, text="Start", command=self.start_deletion
        )
        self.start_button.grid(row=0, column=0, padx=(0, 8))

        self.stop_button = ttk.Button(
            controls_frame, text="Stop", command=self.stop_deletion, state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 8))

        ttk.Button(controls_frame, text="Clear", command=self.clear_text).grid(
            row=0, column=2, padx=(0, 8)
        )

        speed_frame = ttk.Frame(controls_frame)
        speed_frame.grid(row=0, column=3, sticky="we")
        ttk.Label(speed_frame, text="Speed (chars/sec):").grid(row=0, column=0, padx=(0, 6))

        self.speed_var = tk.DoubleVar(value=10.0)
        self.speed_scale = ttk.Scale(
            speed_frame,
            orient="horizontal",
            from_=1,
            to=30,
            variable=self.speed_var,
            command=lambda _event=None: self._update_speed_label(),
        )
        self.speed_scale.grid(row=0, column=1, sticky="we")
        speed_frame.columnconfigure(1, weight=1)

        self.speed_label = ttk.Label(speed_frame, text="10.0")
        self.speed_label.grid(row=0, column=2, padx=(6, 0))

    def start_deletion(self) -> None:
        """Begin deleting characters from the current cursor position."""
        if self.deleting:
            return
        self.deleting = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self._schedule_next_delete()

    def stop_deletion(self) -> None:
        """Stop deleting characters."""
        self.deleting = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def clear_text(self) -> None:
        """Remove all text from the text widget and reset the state."""
        self.stop_deletion()
        self.text.delete("1.0", tk.END)

    def _schedule_next_delete(self) -> None:
        if not self.deleting:
            return

        cps = max(self.speed_var.get(), 0.1)  # Avoid division by zero if slider at minimum.
        delay_ms = int(1000 / cps)
        delay_ms = max(delay_ms, 10)  # Cap minimum delay to avoid event loop overload.

        self.after_id = self.root.after(delay_ms, self._delete_character)

    def _delete_character(self) -> None:
        if not self.deleting:
            return

        # The Text widget always keeps a trailing newline. If nothing but the newline
        # remains we stop.
        last_char_index = self.text.index("end-1c")
        if self.text.compare(last_char_index, "<=", "1.0"):
            self.stop_deletion()
            return

        insert_index = self.text.index(tk.INSERT)
        if self.text.compare(insert_index, ">", last_char_index):
            self.stop_deletion()
            return

        self.text.delete(insert_index)

        # Keep the cursor at the same position after deletion.
        self.text.mark_set(tk.INSERT, insert_index)
        self._schedule_next_delete()

    def _update_speed_label(self) -> None:
        self.speed_label.config(text=f"{self.speed_var.get():.1f}")


def main() -> None:
    root = tk.Tk()
    app = TextDeleterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
