import os
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

try:
    from tkinterdnd2 import DND_FILES, DND_TEXT, TkinterDnD
except ImportError:  # pragma: no cover - helpful message for missing dependency
    raise SystemExit("tkinterdnd2 is required for drag-and-drop support. Install it via 'pip install tkinterdnd2'.")


class ChatObsidianFormatterApp:
    def __init__(self, root: "TkinterDnD.Tk") -> None:
        self.root = root
        self.root.title("Chat → Obsidian Formatter")
        self.root.geometry("760x600")

        style = ttk.Style()
        if "winnative" in style.theme_names():
            style.theme_use("winnative")
        style.configure("Selected.TButton", relief=tk.SUNKEN)

        self.first_heading_level = tk.IntVar(value=1)
        self.sub_heading_level = tk.IntVar(value=2)
        self.first_label = tk.StringVar(value="You said:")
        self.sub_label = tk.StringVar(value="ChatGPT said:")

        self._build_gui()

    def _build_gui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_heading_section(main_frame, "First heading", self.first_heading_level, self.first_label)
        self._build_heading_section(main_frame, "Subsequent headings", self.sub_heading_level, self.sub_label)

        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.text = ScrolledText(text_frame, wrap=tk.WORD, undo=True)
        self.text.pack(fill=tk.BOTH, expand=True)
        self.text.drop_target_register(DND_TEXT, DND_FILES)
        self.text.dnd_bind("<<Drop>>", self.on_drop)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        format_btn = ttk.Button(button_frame, text="Format", command=self.format_text)
        format_btn.pack(side=tk.LEFT, padx=(0, 5))

        copy_btn = ttk.Button(button_frame, text="Copy to clipboard", command=self.copy_to_clipboard)
        copy_btn.pack(side=tk.LEFT)

    def _build_heading_section(
        self,
        parent: ttk.Frame,
        title: str,
        level_var: tk.IntVar,
        label_var: tk.StringVar,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        frame.pack(fill=tk.X, expand=False, pady=(0, 10))

        buttons_frame = ttk.Frame(frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 5))
        buttons = []
        for level in range(1, 7):
            text = "#" * level
            btn = ttk.Button(
                buttons_frame,
                text=text,
                width=5,
                command=lambda lvl=level, btn_index=len(buttons): self._set_heading_level(level_var, lvl, buttons)
            )
            btn.pack(side=tk.LEFT, padx=2)
            buttons.append(btn)

        self._update_heading_buttons(level_var, buttons)
        level_var.trace_add("write", lambda *args, bts=buttons, var=level_var: self._update_heading_buttons(var, bts))

        radios_frame = ttk.Frame(frame)
        radios_frame.pack(fill=tk.X)
        ttk.Radiobutton(radios_frame, text="You said:", variable=label_var, value="You said:").pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ttk.Radiobutton(radios_frame, text="ChatGPT said:", variable=label_var, value="ChatGPT said:").pack(side=tk.LEFT)

    def _update_heading_buttons(self, var: tk.IntVar, buttons: list[ttk.Button]) -> None:
        for idx, btn in enumerate(buttons, start=1):
            if var.get() == idx:
                btn.configure(style="Selected.TButton")
            else:
                btn.configure(style="TButton")

    def _set_heading_level(self, var: tk.IntVar, level: int, buttons: list[ttk.Button]) -> None:
        var.set(level)
        self._update_heading_buttons(var, buttons)

    def on_drop(self, event) -> None:
        data = event.data
        if not data:
            return

        content = None
        cleaned = data
        if cleaned.startswith("{") and cleaned.endswith("}"):
            cleaned = cleaned[1:-1]

        if os.path.exists(cleaned):
            try:
                with open(cleaned, "r", encoding="utf-8") as file:
                    content = file.read()
            except OSError:
                content = None

        if content is None:
            content = data

        if self.text.index(tk.END) != "1.0":
            self.text.insert(tk.END, "\n")
        self.text.insert(tk.END, content)

    def format_text(self) -> None:
        raw = self.text.get("1.0", tk.END)
        lines = raw.splitlines()
        if not lines:
            return

        first_non_empty_idx = next((i for i, line in enumerate(lines) if line.strip()), None)
        if first_non_empty_idx is None:
            return

        trailing_newline = raw.endswith("\n")

        first_heading = f"{'#' * self.first_heading_level.get()} {self.first_label.get()}"
        lines.insert(first_non_empty_idx, first_heading)

        subsequent_heading = f"{'#' * self.sub_heading_level.get()} {self.sub_label.get()}"
        for idx in range(first_non_empty_idx + 1, len(lines)):
            line = lines[idx]
            if line.startswith("You said:") or line.startswith("ChatGPT said:"):
                lines[idx] = subsequent_heading

        formatted = "\n".join(lines)
        if trailing_newline:
            formatted += "\n"

        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", formatted)

    def copy_to_clipboard(self) -> None:
        content = self.text.get("1.0", tk.END)
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        messagebox.showinfo("Copied", "Text copied to clipboard.")


def main() -> None:
    root = TkinterDnD.Tk()
    ChatObsidianFormatterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
