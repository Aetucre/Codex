"""Simple Tkinter application that deletes text incrementally like a delete key."""

import tkinter as tk
from tkinter import ttk


class TextDeleterApp:
    """GUI application that deletes text from the insertion point at a configurable speed."""

    LIGHT_THEME = {
        "bg": "#f6f6f6",
        "fg": "#1a1a1a",
        "text_bg": "#ffffff",
        "text_fg": "#1a1a1a",
        "insert_bg": "#1a1a1a",
        "button_bg": "#e6e6e6",
        "button_active_bg": "#d6d6d6",
        "button_fg": "#1a1a1a",
        "disabled_fg": "#7a7a7a",
        "scale_trough": "#d9d9d9",
        "border": "#c2c2c2",
    }
    DARK_THEME = {
        "bg": "#1d1f21",
        "fg": "#eaeaea",
        "text_bg": "#2c2f33",
        "text_fg": "#f0f0f0",
        "insert_bg": "#f0f0f0",
        "button_bg": "#3a3f45",
        "button_active_bg": "#4b5158",
        "button_fg": "#f0f0f0",
        "disabled_fg": "#8a8f96",
        "scale_trough": "#3d434a",
        "border": "#555b63",
    }

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Incremental Text Deleter")
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.deleting = False
        self.after_id: str | None = None
        self.theme_button_text = tk.StringVar()

        self._build_widgets()
        self._apply_theme(self.dark_mode_var.get())

    def _build_widgets(self) -> None:
        """Create and layout all widgets for the UI."""
        main_frame = ttk.Frame(self.root, padding="16")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(main_frame)
        toolbar.grid(row=0, column=0, sticky="we", pady=(0, 10))
        toolbar.columnconfigure(5, weight=1)

        self.start_button = ttk.Button(toolbar, text="Start", command=self.start_deletion)
        self.start_button.grid(row=0, column=0, padx=(0, 8))

        self.stop_button = ttk.Button(
            toolbar, text="Stop", command=self.stop_deletion, state=tk.DISABLED
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 8))

        ttk.Button(toolbar, text="Clear", command=self.clear_text).grid(
            row=0, column=2, padx=(0, 12)
        )

        speed_frame = ttk.Frame(toolbar)
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
        self.speed_label.grid(row=0, column=2, padx=(6, 12))

        self.dark_mode_var = tk.BooleanVar(value=False)
        self.theme_button_text.set("Dark mode")
        self.theme_button = ttk.Button(
            toolbar,
            textvariable=self.theme_button_text,
            command=self._toggle_theme,
        )
        self.theme_button.grid(row=0, column=4, padx=(0, 12))

        ttk.Label(toolbar, text="Paste text, place cursor, then Start.").grid(
            row=0, column=5, sticky="w"
        )

        self.text = tk.Text(main_frame, wrap="word")
        self.text.grid(row=1, column=0, sticky="nsew")

        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=0, sticky="we", pady=(10, 0))
        self.status_label = ttk.Label(
            status_frame,
            text="Ready. Deletion runs in the background while you keep typing.",
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="we")
        status_frame.columnconfigure(0, weight=1)

    def start_deletion(self) -> None:
        """Begin deleting characters from the current cursor position."""
        if self.deleting:
            return
        self.deleting = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Deleting from the cursor position...")
        self._schedule_next_delete()

    def stop_deletion(self) -> None:
        """Stop deleting characters."""
        self.deleting = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Paused.")
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None

    def clear_text(self) -> None:
        """Remove all text from the text widget and reset the state."""
        self.stop_deletion()
        self.text.delete("1.0", tk.END)
        self.status_label.config(text="Cleared.")

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
            self.status_label.config(text="Nothing left to delete.")
            return

        insert_index = self.text.index(tk.INSERT)
        if self.text.compare(insert_index, ">", last_char_index):
            self.stop_deletion()
            self.status_label.config(text="Cursor is past the end of the text.")
            return

        self.text.delete(insert_index)

        # Keep the cursor at the same position after deletion.
        self.text.mark_set(tk.INSERT, insert_index)
        self._schedule_next_delete()

    def _update_speed_label(self) -> None:
        self.speed_label.config(text=f"{self.speed_var.get():.1f}")

    def _toggle_theme(self) -> None:
        self.dark_mode_var.set(not self.dark_mode_var.get())
        self._apply_theme(self.dark_mode_var.get())

    def _apply_theme(self, dark_mode: bool) -> None:
        colors = self.DARK_THEME if dark_mode else self.LIGHT_THEME
        self.theme_button_text.set("Light mode" if dark_mode else "Dark mode")

        self.root.configure(bg=colors["bg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure(
            "TButton",
            background=colors["button_bg"],
            foreground=colors["button_fg"],
            bordercolor=colors["border"],
            focusthickness=1,
        )
        self.style.map(
            "TButton",
            background=[("active", colors["button_active_bg"])],
            foreground=[("disabled", colors["disabled_fg"])],
        )
        self.style.configure(
            "TCheckbutton",
            background=colors["bg"],
            foreground=colors["fg"],
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", colors["bg"])],
            foreground=[("disabled", colors["disabled_fg"])],
        )
        self.style.configure(
            "Horizontal.TScale",
            background=colors["bg"],
            troughcolor=colors["scale_trough"],
        )
        self.text.configure(
            background=colors["text_bg"],
            foreground=colors["text_fg"],
            insertbackground=colors["insert_bg"],
            highlightbackground=colors["border"],
            highlightcolor=colors["border"],
            highlightthickness=1,
        )


def main() -> None:
    root = tk.Tk()
    app = TextDeleterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
