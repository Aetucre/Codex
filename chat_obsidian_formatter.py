import tkinter as tk
from tkinter import ttk


class HeadingSelector(tk.Frame):
    def __init__(self, master, default_level, default_label, **kwargs):
        super().__init__(master, **kwargs)

        self.level_var = tk.IntVar(value=default_level)
        self.label_var = tk.StringVar(value=default_label)

        self.configure(relief=tk.FLAT)

        # Heading level row
        level_label = tk.Label(self, text="Heading level:")
        level_label.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.level_buttons = []
        for idx in range(6):
            level = idx + 1
            btn = tk.Button(
                self,
                text="#" * level,
                width=6,
                relief=tk.SUNKEN if self.level_var.get() == level else tk.RAISED,
                command=lambda lvl=level: self.set_level(lvl),
            )
            btn.grid(row=0, column=idx + 1, padx=2, pady=2)
            self.level_buttons.append(btn)

        # Label row
        label_label = tk.Label(self, text="Label:")
        label_label.grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(4, 0))

        radio_frame = tk.Frame(self)
        radio_frame.grid(row=1, column=1, columnspan=6, sticky="w", pady=(4, 0))

        you_radio = tk.Radiobutton(
            radio_frame,
            text="You said:",
            variable=self.label_var,
            value="You said:",
        )
        you_radio.pack(side=tk.LEFT, padx=(0, 12))

        chat_radio = tk.Radiobutton(
            radio_frame,
            text="ChatGPT said",
            variable=self.label_var,
            value="ChatGPT said",
        )
        chat_radio.pack(side=tk.LEFT)

    def set_level(self, level):
        self.level_var.set(level)
        for idx, btn in enumerate(self.level_buttons, start=1):
            btn.configure(relief=tk.SUNKEN if idx == level else tk.RAISED)


class ChatObsidianFormatter(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Chat → Obsidian Formatter")

        self.configure(padx=10, pady=10)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # First heading group
        first_frame = tk.LabelFrame(self, text="First heading", padx=10, pady=8, relief=tk.FLAT)
        first_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        first_frame.columnconfigure(0, weight=1)

        self.first_selector = HeadingSelector(first_frame, default_level=1, default_label="You said:")
        self.first_selector.grid(row=0, column=0, sticky="w")

        # Subsequent heading group
        subsequent_frame = tk.LabelFrame(
            self, text="Subsequent headings", padx=10, pady=8, relief=tk.FLAT
        )
        subsequent_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        subsequent_frame.columnconfigure(0, weight=1)

        self.subsequent_selector = HeadingSelector(
            subsequent_frame, default_level=1, default_label="ChatGPT said"
        )
        self.subsequent_selector.grid(row=0, column=0, sticky="w")

        # Text area
        text_frame = tk.Frame(self, relief=tk.GROOVE, bd=1)
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD, undo=True)
        self.text_widget.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        # Buttons
        button_frame = tk.Frame(self)
        button_frame.grid(row=3, column=0, pady=(4, 0))

        format_btn = tk.Button(button_frame, text="Format", width=18, command=self.format_text)
        format_btn.pack(side=tk.LEFT, padx=(0, 8))

        copy_btn = tk.Button(button_frame, text="Copy to clipboard", width=18, command=self.copy_to_clipboard)
        copy_btn.pack(side=tk.LEFT)

        # Make window resizable
        self.minsize(500, 400)

    def format_text(self):
        raw_text = self.text_widget.get("1.0", tk.END)
        lines = raw_text.splitlines(keepends=True)

        first_heading = f"{'#' * self.first_selector.level_var.get()} {self.first_selector.label_var.get()}"
        subsequent_heading = f"{'#' * self.subsequent_selector.level_var.get()} {self.subsequent_selector.label_var.get()}"

        result_lines = []
        first_applied = False

        for line in lines:
            if line.startswith("You said:") or line.startswith("ChatGPT said:"):
                heading_line = first_heading if not first_applied else subsequent_heading
                newline = "\n" if line.endswith("\n") else ""
                result_lines.append(heading_line + newline)
                first_applied = True
            else:
                result_lines.append(line)

        new_text = "".join(result_lines)
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", new_text)

    def copy_to_clipboard(self):
        text = self.text_widget.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()  # ensure clipboard is updated


def main():
    app = ChatObsidianFormatter()
    app.mainloop()


if __name__ == "__main__":
    main()
