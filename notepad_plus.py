#!/usr/bin/env python3
"""Notepad Plus: a Tkinter-based text editor with enhanced delete control.

The Incremental Delete button responds while it is pressed and held. Each
scheduled tick performs a progressively broader deletion that starts with a
single character and grows to entire paragraphs. The progression resets if the
user moves the caret, types text, or 700 ms elapse without another tick. Every
press-and-hold run is wrapped as a single undo block so one undo restores the
removed text.

Persistent settings are stored in a JSON file keyed by:
```
- window.width, window.height, window.x, window.y
- word_wrap: bool
- font.family, font.size
- status.characters, status.words, status.lines
- recent_files: list[str]
- last_folder: str
- speed: int (Incremental Delete slider value)
```
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont


APP_NAME = "Notepad Plus"
CONFIG_FILENAME = "config.json"


@dataclass
class WindowGeometry:
    """Container for window dimensions and placement."""

    width: int = 900
    height: int = 650
    x: Optional[int] = None
    y: Optional[int] = None


def get_config_dir() -> Path:
    """Return the per-user configuration directory."""

    home = Path.home()
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", home))
        return base / "NotepadPlus"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "NotepadPlus"
    return home / ".config" / "notepad_plus"


def load_json_config() -> Dict[str, Any]:
    """Load persisted configuration values or return defaults."""

    config_dir = get_config_dir()
    config_file = config_dir / CONFIG_FILENAME
    defaults = {
        "window": {
            "width": WindowGeometry.width,
            "height": WindowGeometry.height,
            "x": None,
            "y": None,
        },
        "word_wrap": True,
        "font": {
            "family": "",
            "size": 12,
        },
        "status": {
            "characters": True,
            "words": True,
            "lines": True,
        },
        "recent_files": [],
        "last_folder": "",
        "speed": 3,
    }
    if not config_file.exists():
        return defaults
    try:
        with config_file.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return defaults

    def merge(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(base)
        for key, value in extra.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    return merge(defaults, loaded)


def save_json_config(config: Dict[str, Any]) -> None:
    """Persist the configuration to disk."""

    config_dir = get_config_dir()
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    config_file = config_dir / CONFIG_FILENAME
    try:
        with config_file.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
    except OSError:
        messagebox.showwarning(APP_NAME, "Unable to save configuration file.")


class FindReplaceDialog:
    """A simple Find/Replace dialog tied to a text widget."""

    def __init__(self, parent: "NotepadPlus") -> None:
        self.parent = parent
        self.root = tk.Toplevel(parent.root)
        parent.find_dialog = self
        self.root.title("Find / Replace")
        self.root.transient(parent.root)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.find_var = tk.StringVar()
        self.replace_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=False)

        content = ttk.Frame(self.root, padding=12)
        content.grid(row=0, column=0, sticky="nsew")

        ttk.Label(content, text="Find:").grid(row=0, column=0, sticky="w")
        find_entry = ttk.Entry(content, textvariable=self.find_var, width=30)
        find_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=(0, 6))

        ttk.Label(content, text="Replace with:").grid(row=1, column=0, sticky="w")
        replace_entry = ttk.Entry(content, textvariable=self.replace_var, width=30)
        replace_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=(0, 6))

        case_check = ttk.Checkbutton(
            content, text="Case sensitive", variable=self.case_var
        )
        case_check.grid(row=2, column=0, columnspan=4, sticky="w", pady=(0, 8))

        btn_find_next = ttk.Button(content, text="Find Next", command=self.find_next)
        btn_find_prev = ttk.Button(content, text="Find Previous", command=self.find_prev)
        btn_replace = ttk.Button(content, text="Replace", command=self.replace_one)
        btn_replace_all = ttk.Button(
            content, text="Replace All", command=self.replace_all
        )

        btn_find_next.grid(row=3, column=0, padx=2, sticky="ew")
        btn_find_prev.grid(row=3, column=1, padx=2, sticky="ew")
        btn_replace.grid(row=3, column=2, padx=2, sticky="ew")
        btn_replace_all.grid(row=3, column=3, padx=2, sticky="ew")

        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=1)

        self.root.bind("<Return>", lambda *_: self.find_next())
        self.root.bind("<Escape>", lambda *_: self.on_close())

        find_entry.focus_set()

    def destroy(self) -> None:
        self.root.destroy()

    def on_close(self) -> None:
        self.parent.clear_find_highlight()
        self.parent.find_dialog = None
        self.destroy()

    def _search(self, backwards: bool = False) -> bool:
        pattern = self.find_var.get()
        if not pattern:
            return False
        text_widget = self.parent.text
        start_index = text_widget.index("insert")
        if backwards:
            start = text_widget.index(f"{start_index} -1c")
            stop = "1.0"
        else:
            start = start_index
            stop = "end-1c"
        nocase = not self.case_var.get()
        idx = text_widget.search(
            pattern,
            start,
            nocase=nocase,
            stopindex=stop,
            backwards=backwards,
        )
        if not idx:
            wrap_start = "end-1c" if backwards else "1.0"
            wrap_stop = "1.0" if backwards else "end-1c"
            idx = text_widget.search(
                pattern,
                wrap_start,
                nocase=nocase,
                stopindex=wrap_stop,
                backwards=backwards,
            )
        if not idx:
            messagebox.showinfo(APP_NAME, "No further matches found.")
            return False
        end_index = f"{idx}+{len(pattern)}c"
        text_widget.tag_remove("find_highlight", "1.0", "end")
        text_widget.tag_add("find_highlight", idx, end_index)
        insert_target = end_index if not backwards else idx
        text_widget.mark_set("insert", insert_target)
        text_widget.see(idx)
        self.parent.last_find = pattern
        self.parent.last_find_case_sensitive = self.case_var.get()
        return True

    def find_next(self) -> bool:
        return self._search(backwards=False)

    def find_prev(self) -> bool:
        return self._search(backwards=True)

    def replace_one(self) -> None:
        text_widget = self.parent.text
        pattern = self.find_var.get()
        replacement = self.replace_var.get()
        if not pattern:
            return
        ranges = text_widget.tag_ranges("sel")
        if ranges:
            selected_text = text_widget.get(ranges[0], ranges[1])
            if self.case_var.get():
                selected_cmp = selected_text
                pattern_cmp = pattern
            else:
                selected_cmp = selected_text.lower()
                pattern_cmp = pattern.lower()
            if selected_cmp == pattern_cmp:
                text_widget.delete(ranges[0], ranges[1])
                text_widget.insert(ranges[0], replacement)
                text_widget.tag_remove("find_highlight", "1.0", "end")
                new_end = f"{ranges[0]}+{len(replacement)}c"
                text_widget.tag_add("find_highlight", ranges[0], new_end)
                text_widget.mark_set("insert", new_end)
                return
        found = self.find_next()
        if found:
            self.replace_one()

    def replace_all(self) -> None:
        pattern = self.find_var.get()
        if not pattern:
            return
        replacement = self.replace_var.get()
        text_widget = self.parent.text
        content = text_widget.get("1.0", "end-1c")
        if not content:
            return
        flags = 0 if self.case_var.get() else re.IGNORECASE
        try:
            regex = re.compile(re.escape(pattern), flags)
        except re.error:
            messagebox.showerror(APP_NAME, "Invalid search pattern.")
            return
        new_content, count = regex.subn(replacement, content)
        if count == 0:
            messagebox.showinfo(APP_NAME, "No matches were replaced.")
            return
        self.parent.suspend_modified_event = True
        text_widget.delete("1.0", "end")
        text_widget.insert("1.0", new_content)
        text_widget.edit_modified(True)
        self.parent.suspend_modified_event = False
        self.parent.dirty = True
        self.parent.update_title()
        self.parent.schedule_status_update()
        messagebox.showinfo(APP_NAME, f"Replaced {count} occurrences.")


class NotepadPlus:
    """Primary application class for the Notepad Plus editor."""

    SPEED_INTERVALS = {1: 600, 2: 400, 3: 250, 4: 150, 5: 90}

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Untitled — {APP_NAME}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config_data = load_json_config()

        self.filepath: Optional[Path] = None
        self.dirty = False
        self.suspend_modified_event = False
        self.status_update_job: Optional[str] = None
        self.stage_reset_job: Optional[str] = None
        self.incremental_job: Optional[str] = None
        self.incremental_active = False
        self.incremental_stage = 1
        self.find_dialog: Optional[FindReplaceDialog] = None
        self.last_find: Optional[str] = None
        self.last_find_case_sensitive = False

        self.font_family_var = tk.StringVar()
        self.font_size_var = tk.StringVar()
        self.word_wrap_var = tk.BooleanVar(value=True)
        self.show_chars_var = tk.BooleanVar(value=True)
        self.show_words_var = tk.BooleanVar(value=True)
        self.show_lines_var = tk.BooleanVar(value=True)
        self.speed_var = tk.IntVar(value=3)

        self.create_widgets()
        self.apply_config()
        self.new_file()

    # ------------------------------------------------------------------
    # Widget creation and layout
    # ------------------------------------------------------------------
    def create_widgets(self) -> None:
        self.create_menus()
        self.toolbar = ttk.Frame(self.root, padding=(6, 4))
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        inc_button = ttk.Button(
            self.toolbar, text="Incremental Delete", takefocus=False
        )
        inc_button.bind("<ButtonPress-1>", self.start_incremental_delete)
        inc_button.bind("<ButtonRelease-1>", self.stop_incremental_delete)
        inc_button.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Label(self.toolbar, text="Speed:").pack(side=tk.LEFT)
        self.speed_slider = tk.Scale(
            self.toolbar,
            from_=1,
            to=5,
            orient=tk.HORIZONTAL,
            variable=self.speed_var,
            showvalue=True,
            length=140,
        )
        self.speed_slider.pack(side=tk.LEFT)

        fonts_frame = ttk.Frame(self.toolbar)
        fonts_frame.pack(side=tk.LEFT, padx=(12, 0))

        ttk.Label(fonts_frame, text="Font:").pack(side=tk.LEFT)
        self.font_family_combo = ttk.Combobox(
            fonts_frame,
            textvariable=self.font_family_var,
            state="readonly",
            width=24,
        )
        self.font_family_combo.pack(side=tk.LEFT, padx=(4, 4))
        self.font_family_combo.bind("<<ComboboxSelected>>", self.on_font_change)

        ttk.Label(fonts_frame, text="Size:").pack(side=tk.LEFT)
        self.font_size_combo = ttk.Combobox(
            fonts_frame,
            textvariable=self.font_size_var,
            values=[str(n) for n in range(8, 49)],
            width=4,
        )
        self.font_size_combo.pack(side=tk.LEFT)
        self.font_size_combo.bind("<<ComboboxSelected>>", self.on_font_change)
        self.font_size_combo.bind("<Return>", self.on_font_change)
        self.font_size_combo.bind("<FocusOut>", self.on_font_change)

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.text_font = tkfont.Font(family="TkDefaultFont", size=12)
        self.text = tk.Text(
            self.main_frame,
            undo=True,
            autoseparators=True,
            wrap=tk.WORD,
            font=self.text_font,
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            self.main_frame, orient=tk.VERTICAL, command=self.text.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.tag_configure("find_highlight", background="#fef49c")

        self.text.bind("<<Modified>>", self.on_text_modified)
        self.text.bind("<KeyRelease>", self.on_cursor_activity, add="+")
        self.text.bind("<ButtonRelease-1>", self.on_cursor_activity, add="+")
        self.text.bind("<<Selection>>", self.on_cursor_activity, add="+")

        self.text.focus_set()
        self.create_status_bar()

    def create_menus(self) -> None:
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        self.file_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(
            label="New", command=self.new_file, accelerator="Ctrl+N"
        )
        self.file_menu.add_command(
            label="Open…", command=self.open_file_dialog, accelerator="Ctrl+O"
        )
        self.file_menu.add_command(
            label="Save", command=self.save_file, accelerator="Ctrl+S"
        )
        self.file_menu.add_command(
            label="Save As…",
            command=self.save_file_as,
            accelerator="Ctrl+Shift+S",
        )
        self.file_menu.add_separator()
        self.recent_menu = tk.Menu(self.file_menu, tearoff=False)
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_close)

    def create_status_bar(self) -> None:
        self.status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(6, 2))
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.counter_frame = ttk.Frame(self.status_frame)
        self.counter_frame.pack(side=tk.LEFT)

        self.char_label = ttk.Label(self.counter_frame, text="Chars: 0")
        self.word_label = ttk.Label(self.counter_frame, text="Words: 0")
        self.line_label = ttk.Label(self.counter_frame, text="Lines: 0")

        self.checkbox_frame = ttk.Frame(self.status_frame)
        self.checkbox_frame.pack(side=tk.RIGHT)
        ttk.Checkbutton(
            self.checkbox_frame,
            text="Show Characters",
            variable=self.show_chars_var,
            command=self.on_status_toggle,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            self.checkbox_frame,
            text="Show Words",
            variable=self.show_words_var,
            command=self.on_status_toggle,
        ).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(
            self.checkbox_frame,
            text="Show Lines",
            variable=self.show_lines_var,
            command=self.on_status_toggle,
        ).pack(side=tk.LEFT, padx=4)
        self.edit_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)
        self.edit_menu.add_command(
            label="Undo", command=self.text.edit_undo, accelerator="Ctrl+Z"
        )
        self.edit_menu.add_command(
            label="Redo", command=self.text.edit_redo, accelerator="Ctrl+Y"
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label="Cut",
            command=lambda: self.text.event_generate("<<Cut>>"),
            accelerator="Ctrl+X",
        )
        self.edit_menu.add_command(
            label="Copy",
            command=lambda: self.text.event_generate("<<Copy>>"),
            accelerator="Ctrl+C",
        )
        self.edit_menu.add_command(
            label="Paste",
            command=lambda: self.text.event_generate("<<Paste>>"),
            accelerator="Ctrl+V",
        )
        self.edit_menu.add_command(
            label="Select All",
            command=lambda: self.text.tag_add("sel", "1.0", "end"),
            accelerator="Ctrl+A",
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label="Find / Replace",
            command=self.show_find_dialog,
            accelerator="Ctrl+F",
        )
        self.edit_menu.add_command(
            label="Find Next", command=self.find_next, accelerator="F3"
        )

        self.view_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_checkbutton(
            label="Word Wrap",
            variable=self.word_wrap_var,
            command=self.toggle_word_wrap,
        )
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(
            label="Show Characters",
            variable=self.show_chars_var,
            command=self.on_status_toggle,
        )
        self.view_menu.add_checkbutton(
            label="Show Words",
            variable=self.show_words_var,
            command=self.on_status_toggle,
        )
        self.view_menu.add_checkbutton(
            label="Show Lines",
            variable=self.show_lines_var,
            command=self.on_status_toggle,
        )

        help_menu = tk.Menu(self.menubar, tearoff=False)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        self.bind_shortcuts()

    def bind_shortcuts(self) -> None:
        bindings = {
            "<Control-n>": self.new_file,
            "<Control-o>": self.open_file_dialog,
            "<Control-s>": self.save_file,
            "<Control-Shift-s>": self.save_file_as,
            "<Control-f>": self.show_find_dialog,
            "<F3>": self.find_next,
        }
        if sys.platform == "darwin":
            mac_bindings = {
                "<Command-n>": self.new_file,
                "<Command-o>": self.open_file_dialog,
                "<Command-s>": self.save_file,
                "<Command-Shift-s>": self.save_file_as,
                "<Command-f>": self.show_find_dialog,
            }
            bindings.update(mac_bindings)
        for sequence, func in bindings.items():
            self.root.bind(
                sequence,
                lambda event, callback=func: self._event_wrapper(callback),
            )

    def _event_wrapper(self, callback) -> str:
        callback()
        return "break"
    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def apply_config(self) -> None:
        window = self.config_data.get("window", {})
        geometry = WindowGeometry(
            width=window.get("width", WindowGeometry.width),
            height=window.get("height", WindowGeometry.height),
            x=window.get("x"),
            y=window.get("y"),
        )
        geometry_str = f"{geometry.width}x{geometry.height}"
        if geometry.x is not None and geometry.y is not None:
            geometry_str += f"+{geometry.x}+{geometry.y}"
        self.root.geometry(geometry_str)

        font_families = sorted(set(tkfont.families()))
        self.font_family_combo["values"] = font_families

        font_cfg = self.config_data.get("font", {})
        family = font_cfg.get("family")
        if not family or family not in font_families:
            family = tkfont.nametofont("TkDefaultFont").actual("family")
        size = int(font_cfg.get("size", 12))
        self.font_family_var.set(family)
        self.font_size_var.set(str(size))
        self.text_font.config(family=family, size=size)

        self.word_wrap_var.set(self.config_data.get("word_wrap", True))
        self.toggle_word_wrap()

        status_cfg = self.config_data.get("status", {})
        self.show_chars_var.set(bool(status_cfg.get("characters", True)))
        self.show_words_var.set(bool(status_cfg.get("words", True)))
        self.show_lines_var.set(bool(status_cfg.get("lines", True)))
        self.update_status_visibility()

        speed = int(self.config_data.get("speed", 3))
        if speed not in self.SPEED_INTERVALS:
            speed = 3
        self.speed_var.set(speed)

        self.recent_files = [
            path
            for path in self.config_data.get("recent_files", [])
            if Path(path).exists()
        ][:5]
        self.rebuild_recent_menu()

        self.last_folder = self.config_data.get("last_folder", "")

    def update_config(self) -> None:
        window_state = self.root.winfo_geometry()
        dims, _, _pos = window_state.partition("+")
        width_str, _, height_str = dims.partition("x")
        try:
            width = int(width_str)
            height = int(height_str)
        except ValueError:
            width = WindowGeometry.width
            height = WindowGeometry.height
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.config_data["window"] = {
            "width": width,
            "height": height,
            "x": x,
            "y": y,
        }
        self.config_data["word_wrap"] = self.word_wrap_var.get()
        self.config_data["font"] = {
            "family": self.font_family_var.get(),
            "size": int(self.font_size_var.get() or 12),
        }
        self.config_data["status"] = {
            "characters": self.show_chars_var.get(),
            "words": self.show_words_var.get(),
            "lines": self.show_lines_var.get(),
        }
        self.config_data["recent_files"] = self.recent_files[:5]
        self.config_data["last_folder"] = self.last_folder
        self.config_data["speed"] = self.speed_var.get()
    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------
    def new_file(self, *_args) -> None:
        if not self.maybe_save_changes():
            return
        self.suspend_modified_event = True
        self.text.delete("1.0", tk.END)
        self.text.edit_modified(False)
        self.suspend_modified_event = False
        self.filepath = None
        self.dirty = False
        self.update_title()
        self.schedule_status_update()
        self.text.focus_set()

    def open_file_dialog(self, *_args) -> None:
        if not self.maybe_save_changes():
            return
        initialdir = self.last_folder or None
        path = filedialog.askopenfilename(initialdir=initialdir)
        if not path:
            return
        self.open_file(Path(path))

    def open_file(self, path: Path) -> None:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            messagebox.showerror(APP_NAME, f"Failed to open file:\n{exc}")
            return
        self.suspend_modified_event = True
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content)
        self.text.edit_modified(False)
        self.suspend_modified_event = False
        self.text.mark_set("insert", "1.0")
        self.text.see("1.0")
        self.filepath = path
        self.dirty = False
        self.add_to_recent(path)
        self.last_folder = str(path.parent)
        self.update_title()
        self.schedule_status_update()
        self.text.focus_set()

    def save_file(self, *_args) -> bool:
        if self.filepath is None:
            return self.save_file_as()
        return self.write_to_path(self.filepath)

    def save_file_as(self, *_args) -> bool:
        initialdir = self.last_folder or None
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            initialdir=initialdir,
        )
        if not path:
            return False
        saved = self.write_to_path(Path(path))
        if saved:
            self.filepath = Path(path)
            self.last_folder = str(self.filepath.parent)
            self.add_to_recent(self.filepath)
        return saved

    def write_to_path(self, path: Path) -> bool:
        content = self.text.get("1.0", "end-1c")
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"Failed to save file:\n{exc}")
            return False
        self.filepath = path
        self.text.edit_modified(False)
        self.dirty = False
        self.update_title()
        return True

    def add_to_recent(self, path: Path) -> None:
        path_str = str(path)
        if path_str in getattr(self, "recent_files", []):
            self.recent_files.remove(path_str)
        else:
            self.recent_files = getattr(self, "recent_files", [])
        self.recent_files.insert(0, path_str)
        self.recent_files = self.recent_files[:5]
        self.rebuild_recent_menu()

    def rebuild_recent_menu(self) -> None:
        self.recent_menu.delete(0, tk.END)
        if not getattr(self, "recent_files", []):
            self.recent_menu.add_command(label="(Empty)", state=tk.DISABLED)
            return
        for path in self.recent_files:
            self.recent_menu.add_command(
                label=path,
                command=lambda p=path: self.open_recent(Path(p)),
            )

    def open_recent(self, path: Path) -> None:
        if not path.exists():
            messagebox.showwarning(APP_NAME, "File not found. Removing from list.")
            if str(path) in self.recent_files:
                self.recent_files.remove(str(path))
                self.rebuild_recent_menu()
            return
        if not self.maybe_save_changes():
            return
        self.open_file(path)

    def maybe_save_changes(self) -> bool:
        if not self.dirty:
            return True
        name = self.filepath.name if self.filepath else "Untitled"
        response = messagebox.askyesnocancel(
            APP_NAME,
            f"Save changes to {name}?",
            default=messagebox.YES,
        )
        if response is None:
            return False
        if response:
            return self.save_file()
        return True

    def update_title(self) -> None:
        name = self.filepath.name if self.filepath else "Untitled"
        if self.dirty:
            name += "*"
        self.root.title(f"{name} — {APP_NAME}")
    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def on_text_modified(self, *_args) -> None:
        if self.suspend_modified_event:
            self.text.edit_modified(False)
            return
        if self.text.edit_modified():
            self.text.edit_modified(False)
            if not self.incremental_active:
                self.force_stage_reset()
            self.dirty = True
            self.update_title()
            self.schedule_status_update()

    def on_cursor_activity(self, *_args) -> None:
        if not self.incremental_active:
            self.force_stage_reset()
        self.schedule_status_update()

    def schedule_status_update(self) -> None:
        if self.status_update_job is not None:
            self.root.after_cancel(self.status_update_job)
        self.status_update_job = self.root.after(120, self.update_status_counts)

    def update_status_counts(self) -> None:
        self.status_update_job = None
        content = self.text.get("1.0", "end-1c")
        char_count = len(content)
        words = content.split()
        word_count = len(words)
        if content:
            line_count = content.count("\n") + 1
        else:
            line_count = 0
        self.char_label.config(text=f"Chars: {char_count}")
        self.word_label.config(text=f"Words: {word_count}")
        self.line_label.config(text=f"Lines: {line_count}")
        self.update_status_visibility()

    def on_status_toggle(self) -> None:
        self.update_status_visibility()
        self.schedule_status_update()

    def update_status_visibility(self) -> None:
        for label in (self.char_label, self.word_label, self.line_label):
            label.pack_forget()
        if self.show_chars_var.get():
            self.char_label.pack(side=tk.LEFT, padx=6)
        if self.show_words_var.get():
            self.word_label.pack(side=tk.LEFT, padx=6)
        if self.show_lines_var.get():
            self.line_label.pack(side=tk.LEFT, padx=6)
        any_displayed = (
            self.show_chars_var.get()
            or self.show_words_var.get()
            or self.show_lines_var.get()
        )
        if any_displayed:
            if not self.counter_frame.winfo_ismapped():
                self.counter_frame.pack(side=tk.LEFT)
            if not self.checkbox_frame.winfo_ismapped():
                self.checkbox_frame.pack(side=tk.RIGHT)
            self.status_frame.configure(height="")
            self.status_frame.pack_propagate(True)
        else:
            if self.counter_frame.winfo_ismapped():
                self.counter_frame.pack_forget()
            if self.checkbox_frame.winfo_ismapped():
                self.checkbox_frame.pack_forget()
            self.status_frame.configure(height=1)
            self.status_frame.pack_propagate(False)

    def toggle_word_wrap(self) -> None:
        wrap = tk.WORD if self.word_wrap_var.get() else tk.NONE
        self.text.configure(wrap=wrap)

    def on_font_change(self, *_args) -> None:
        family = self.font_family_var.get()
        size_str = self.font_size_var.get()
        try:
            size = int(size_str)
        except (TypeError, ValueError):
            size = 12
            self.font_size_var.set(str(size))
        self.text_font.config(family=family, size=size)

    # ------------------------------------------------------------------
    # Incremental delete handling
    # ------------------------------------------------------------------
    def start_incremental_delete(self, *_args) -> None:
        if self.incremental_active:
            return
        self.text.focus_set()
        self.incremental_active = True
        self.incremental_stage = 1
        self.text.edit_separator()
        self.cancel_stage_reset()
        self.run_incremental_tick()

    def run_incremental_tick(self) -> None:
        if not self.incremental_active:
            return
        performed = self.perform_incremental_stage(self.incremental_stage)
        self.schedule_status_update()
        if not performed and self.text.compare("insert", "==", "1.0"):
            self.stop_incremental_delete()
            return
        if self.incremental_stage < 5:
            self.incremental_stage += 1
        interval = self.get_speed_interval()
        self.incremental_job = self.root.after(interval, self.run_incremental_tick)
        self.schedule_stage_reset()

    def stop_incremental_delete(self, *_args) -> None:
        if not self.incremental_active:
            return
        self.incremental_active = False
        if self.incremental_job is not None:
            self.root.after_cancel(self.incremental_job)
            self.incremental_job = None
        self.text.edit_separator()
        self.force_stage_reset()

    def get_speed_interval(self) -> int:
        value = self.speed_var.get()
        return self.SPEED_INTERVALS.get(value, 400)

    def cancel_stage_reset(self) -> None:
        if self.stage_reset_job is not None:
            self.root.after_cancel(self.stage_reset_job)
            self.stage_reset_job = None

    def schedule_stage_reset(self) -> None:
        self.cancel_stage_reset()
        self.stage_reset_job = self.root.after(700, self._stage_timeout)

    def _stage_timeout(self) -> None:
        self.stage_reset_job = None
        if not self.incremental_active:
            self.incremental_stage = 1

    def force_stage_reset(self) -> None:
        self.cancel_stage_reset()
        if not self.incremental_active:
            self.incremental_stage = 1

    def perform_incremental_stage(self, stage: int) -> bool:
        text = self.text
        if stage == 1:
            if text.compare("insert", "==", "1.0"):
                return False
            text.delete("insert -1c", "insert")
            return True
        if stage == 2:
            before = text.get("1.0", "insert")
            if not before:
                return False
            idx = len(before)
            j = idx
            while j > 0 and before[j - 1].isspace():
                j -= 1
            k = j
            while k > 0 and not before[k - 1].isspace():
                k -= 1
            delete_count = idx - k
            if delete_count <= 0:
                return False
            text.delete(f"insert-{delete_count}c", "insert")
            return True
        if stage == 3:
            line_start = text.index("insert linestart")
            if text.compare(line_start, "==", "insert"):
                return False
            text.delete(line_start, "insert")
            return True
        if stage == 4:
            line_start = text.index("insert linestart")
            if text.compare(line_start, "==", "1.0"):
                return False
            prev_char_index = text.index(f"{line_start} -1c")
            prev_char = text.get(prev_char_index, line_start)
            if prev_char != "\n":
                return False
            text.delete(prev_char_index, line_start)
            return True
        if stage == 5:
            before = text.get("1.0", "insert")
            if not before:
                return False
            trimmed = before.rstrip("\n")
            marker = trimmed.rfind("\n\n")
            if marker == -1:
                text.delete("1.0", "insert")
                return True
            start_index = marker + 2
            delete_count = len(before) - start_index
            if delete_count <= 0:
                return False
            text.delete(f"insert-{delete_count}c", "insert")
            return True
        return False
    # ------------------------------------------------------------------
    # Find/replace helpers
    # ------------------------------------------------------------------
    def clear_find_highlight(self) -> None:
        self.text.tag_remove("find_highlight", "1.0", "end")

    def show_find_dialog(self, *_args) -> None:
        if self.find_dialog is not None:
            self.find_dialog.root.deiconify()
            self.find_dialog.root.lift()
            return
        FindReplaceDialog(self)

    def find_next(self, *_args) -> None:
        self.search_with_last(backwards=False)

    def search_with_last(self, backwards: bool) -> None:
        if not self.last_find:
            self.show_find_dialog()
            return
        start_index = self.text.index("insert")
        if backwards:
            start = self.text.index(f"{start_index} -1c")
            stop = "1.0"
        else:
            start = start_index
            stop = "end-1c"
        nocase = not self.last_find_case_sensitive
        idx = self.text.search(
            self.last_find,
            start,
            nocase=nocase,
            stopindex=stop,
            backwards=backwards,
        )
        if not idx:
            wrap_start = "end-1c" if backwards else "1.0"
            wrap_stop = "1.0" if backwards else "end-1c"
            idx = self.text.search(
                self.last_find,
                wrap_start,
                nocase=nocase,
                stopindex=wrap_stop,
                backwards=backwards,
            )
        if not idx:
            messagebox.showinfo(APP_NAME, "No matches found.")
            return
        end_index = f"{idx}+{len(self.last_find)}c"
        self.text.tag_remove("find_highlight", "1.0", "end")
        self.text.tag_add("find_highlight", idx, end_index)
        insert_target = end_index if not backwards else idx
        self.text.mark_set("insert", insert_target)
        self.text.see(idx)

    # ------------------------------------------------------------------
    # Miscellaneous helpers
    # ------------------------------------------------------------------
    def show_about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "Notepad Plus\nA lightweight Tkinter text editor with"
            " incremental deletion.",
        )

    def on_close(self) -> None:
        if not self.maybe_save_changes():
            return
        self.update_config()
        save_json_config(self.config_data)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = NotepadPlus(root)
    root.mainloop()


if __name__ == "__main__":
    main()
