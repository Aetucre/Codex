import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

DATA_FILE = Path("visited_establishments.json")


@dataclass
class Visit:
    date: str
    liked: str
    disliked: str


@dataclass
class Establishment:
    name: str
    type: str
    visits: list


class VisitTrackerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Restaurant & Hotel Visit Tracker")
        self.root.geometry("850x550")

        self.establishments: dict[str, Establishment] = {}
        self.load_data()

        self.build_ui()
        self.refresh_dropdown()

    def build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        add_section = ttk.LabelFrame(main, text="Add Establishment", padding=12)
        add_section.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(add_section, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_var = tk.StringVar()
        ttk.Entry(add_section, textvariable=self.name_var, width=36).grid(row=0, column=1, padx=8)

        ttk.Label(add_section, text="Type:").grid(row=0, column=2, sticky=tk.W)
        self.type_var = tk.StringVar(value="Restaurant")
        ttk.Combobox(
            add_section,
            textvariable=self.type_var,
            values=["Restaurant", "Hotel"],
            state="readonly",
            width=15,
        ).grid(row=0, column=3, padx=8)

        ttk.Button(add_section, text="Add", command=self.add_establishment).grid(row=0, column=4)

        visit_section = ttk.LabelFrame(main, text="Log Visit", padding=12)
        visit_section.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(visit_section, text="Select establishment:").grid(row=0, column=0, sticky=tk.W)
        self.selected_establishment = tk.StringVar()
        self.dropdown = ttk.Combobox(visit_section, textvariable=self.selected_establishment, state="readonly", width=40)
        self.dropdown.grid(row=0, column=1, padx=8)
        self.dropdown.bind("<<ComboboxSelected>>", lambda _: self.render_visit_history())

        ttk.Label(visit_section, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky=tk.W, pady=(8, 0))
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(visit_section, textvariable=self.date_var, width=20).grid(row=1, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Label(visit_section, text="Liked (menu/accommodations/amenities):").grid(row=2, column=0, sticky=tk.NW, pady=(8, 0))
        self.liked_text = tk.Text(visit_section, height=4, width=50)
        self.liked_text.grid(row=2, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Label(visit_section, text="Did not like:").grid(row=3, column=0, sticky=tk.NW, pady=(8, 0))
        self.disliked_text = tk.Text(visit_section, height=4, width=50)
        self.disliked_text.grid(row=3, column=1, sticky=tk.W, pady=(8, 0))

        ttk.Button(visit_section, text="Add Visit", command=self.add_visit).grid(row=4, column=1, sticky=tk.E, pady=(8, 0))

        history_section = ttk.LabelFrame(main, text="Visit History", padding=12)
        history_section.pack(fill=tk.BOTH, expand=True)

        self.history = tk.Text(history_section, state=tk.DISABLED, wrap=tk.WORD)
        self.history.pack(fill=tk.BOTH, expand=True)

    def load_data(self) -> None:
        if not DATA_FILE.exists():
            return
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for est in raw:
            self.establishments[est["name"]] = Establishment(
                name=est["name"],
                type=est["type"],
                visits=est.get("visits", []),
            )

    def save_data(self) -> None:
        data = [asdict(est) for est in self.establishments.values()]
        DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def add_establishment(self) -> None:
        name = self.name_var.get().strip()
        est_type = self.type_var.get().strip()

        if not name:
            messagebox.showerror("Validation error", "Please enter a name.")
            return
        if name in self.establishments:
            messagebox.showerror("Duplicate", "That establishment already exists.")
            return

        self.establishments[name] = Establishment(name=name, type=est_type, visits=[])
        self.save_data()
        self.refresh_dropdown(select=name)
        self.name_var.set("")

    def refresh_dropdown(self, select: str | None = None) -> None:
        names = sorted(self.establishments.keys())
        self.dropdown["values"] = names

        if select:
            self.selected_establishment.set(select)
        elif names and not self.selected_establishment.get():
            self.selected_establishment.set(names[0])

        self.render_visit_history()

    def add_visit(self) -> None:
        selected = self.selected_establishment.get().strip()
        if not selected:
            messagebox.showerror("Validation error", "Please choose an establishment.")
            return

        visit_date = self.date_var.get().strip()
        try:
            datetime.strptime(visit_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Validation error", "Date must be YYYY-MM-DD.")
            return

        liked = self.liked_text.get("1.0", tk.END).strip()
        disliked = self.disliked_text.get("1.0", tk.END).strip()

        if not liked and not disliked:
            messagebox.showerror("Validation error", "Please add liked or disliked notes.")
            return

        visit = Visit(date=visit_date, liked=liked, disliked=disliked)
        self.establishments[selected].visits.append(asdict(visit))
        self.save_data()

        self.liked_text.delete("1.0", tk.END)
        self.disliked_text.delete("1.0", tk.END)
        self.render_visit_history()

    def render_visit_history(self) -> None:
        selected = self.selected_establishment.get().strip()
        self.history.configure(state=tk.NORMAL)
        self.history.delete("1.0", tk.END)

        if not selected or selected not in self.establishments:
            self.history.insert(tk.END, "No establishment selected.")
            self.history.configure(state=tk.DISABLED)
            return

        est = self.establishments[selected]
        self.history.insert(tk.END, f"{est.name} ({est.type})\n")
        self.history.insert(tk.END, "-" * 60 + "\n")

        if not est.visits:
            self.history.insert(tk.END, "No visits recorded yet.")
            self.history.configure(state=tk.DISABLED)
            return

        for i, visit in enumerate(sorted(est.visits, key=lambda v: v["date"], reverse=True), start=1):
            self.history.insert(tk.END, f"Visit #{i} - {visit['date']}\n")
            self.history.insert(tk.END, f"  Liked: {visit.get('liked', '') or '—'}\n")
            self.history.insert(tk.END, f"  Did not like: {visit.get('disliked', '') or '—'}\n")
            self.history.insert(tk.END, "\n")

        self.history.configure(state=tk.DISABLED)


if __name__ == "__main__":
    root = tk.Tk()
    app = VisitTrackerApp(root)
    root.mainloop()
