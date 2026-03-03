#!/usr/bin/env python3
"""Read ChatGPT export JSON and surface regeneration branches.

Supports:
- conversations.json files
- export directories containing conversations.json
- .zip exports containing conversations.json

Can also start without arguments and open a file picker.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RegenVariant:
    index: int
    total: int
    node_id: str
    role: str
    created_at: str
    excerpt: str


@dataclass
class RegenPoint:
    parent_id: str
    parent_role: str
    variants: list[RegenVariant]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect ChatGPT export conversations and list regeneration branches."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="",
        help=(
            "Path to conversations.json, an export directory, or export .zip. "
            "If omitted, a file picker opens."
        ),
    )
    parser.add_argument(
        "--date-query",
        default="",
        help="Date fragment to search (e.g. 050724 as MMDDYY).",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        default=25,
        help="Maximum matching conversations to print (default: 25)",
    )
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="Also print root-to-leaf branch paths.",
    )
    return parser.parse_args()


def pick_input_path() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception:
        return ""

    try:
        root = tk.Tk()
        root.withdraw()
        path = filedialog.askopenfilename(
            title="Select ChatGPT export file",
            filetypes=[
                ("ChatGPT exports", "*.json *.zip"),
                ("JSON files", "*.json"),
                ("ZIP files", "*.zip"),
                ("All files", "*.*"),
            ],
        )
        root.destroy()
        return path
    except Exception:
        return ""


def load_conversations_from_path(raw_input: str) -> list[dict[str, Any]]:
    path = Path(raw_input).expanduser().resolve()

    if path.is_dir():
        target = path / "conversations.json"
        if not target.exists():
            raise FileNotFoundError(f"No conversations.json found in directory: {path}")
        return load_conversations_file(target)

    if not path.exists():
        raise FileNotFoundError(f"Could not find input path: {path}")

    if path.suffix.lower() == ".zip":
        return load_conversations_zip(path)

    return load_conversations_file(path)


def load_conversations_file(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(
            "Expected JSON array of conversations. "
            "If this is a ChatGPT export, choose conversations.json."
        )
    return data


def load_conversations_zip(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path, "r") as zf:
        names = zf.namelist()
        exact = [n for n in names if n.endswith("conversations.json")]
        if not exact:
            raise FileNotFoundError("No conversations.json found inside the zip file.")
        chosen = exact[0]
        with zf.open(chosen, "r") as f:
            raw = f.read()

    data = json.load(io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("conversations.json inside zip is not a JSON array.")
    return data


def ts_to_str(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    try:
        return datetime.utcfromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(value)


def ts_to_mmddyy(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return datetime.utcfromtimestamp(float(value)).strftime("%m%d%y")
    except Exception:
        return ""


def node_text(node: dict[str, Any]) -> str:
    message = node.get("message") or {}
    content = message.get("content") or {}
    parts = content.get("parts")
    if isinstance(parts, list):
        text = " ".join(str(p) for p in parts if p is not None)
    else:
        text = content.get("text") or ""
    text = " ".join(str(text).split())
    return text[:120] + ("…" if len(text) > 120 else "")


def node_role(node: dict[str, Any]) -> str:
    message = node.get("message") or {}
    author = message.get("author") or {}
    return str(author.get("role") or "unknown")


def get_roots(mapping: dict[str, dict[str, Any]]) -> list[str]:
    return [node_id for node_id, node in mapping.items() if node.get("parent") is None]


def enumerate_paths(mapping: dict[str, dict[str, Any]]) -> list[list[str]]:
    paths: list[list[str]] = []

    def dfs(node_id: str, current: list[str]) -> None:
        node = mapping.get(node_id, {})
        children = node.get("children") or []
        current.append(node_id)
        if not children:
            paths.append(current.copy())
        else:
            for child_id in children:
                if child_id in mapping:
                    dfs(child_id, current)
        current.pop()

    for root in get_roots(mapping):
        dfs(root, [])
    return paths


def find_regeneration_points(mapping: dict[str, dict[str, Any]]) -> list[RegenPoint]:
    points: list[RegenPoint] = []

    for parent_id, parent in mapping.items():
        child_ids = parent.get("children") or []
        assistant_children = [
            child_id
            for child_id in child_ids
            if child_id in mapping and node_role(mapping[child_id]) == "assistant"
        ]
        if len(assistant_children) < 2:
            continue

        assistant_children.sort(
            key=lambda node_id: (
                (mapping[node_id].get("message") or {}).get("create_time") or float("inf"),
                node_id,
            )
        )

        variants: list[RegenVariant] = []
        total = len(assistant_children)
        for i, node_id in enumerate(assistant_children, start=1):
            child = mapping[node_id]
            created = (child.get("message") or {}).get("create_time")
            variants.append(
                RegenVariant(
                    index=i,
                    total=total,
                    node_id=node_id,
                    role=node_role(child),
                    created_at=ts_to_str(created),
                    excerpt=node_text(child),
                )
            )

        points.append(
            RegenPoint(
                parent_id=parent_id,
                parent_role=node_role(parent),
                variants=variants,
            )
        )

    return points


def matches_date_query(conv: dict[str, Any], mapping: dict[str, dict[str, Any]], query: str) -> bool:
    if not query:
        return True

    q = query.strip().lower()
    if q in str(conv.get("title") or "").lower():
        return True

    if q in {ts_to_mmddyy(conv.get("create_time")), ts_to_mmddyy(conv.get("update_time"))}:
        return True

    for node in mapping.values():
        created = (node.get("message") or {}).get("create_time")
        if ts_to_mmddyy(created) == q:
            return True

    return False


def print_conversation(conv: dict[str, Any], show_paths: bool) -> bool:
    mapping = conv.get("mapping") or {}
    if not isinstance(mapping, dict) or not mapping:
        return False

    regen_points = find_regeneration_points(mapping)
    if not regen_points:
        return False

    print("=" * 80)
    print(f"Conversation: {conv.get('title') or '(untitled)'}")
    print(f"ID: {conv.get('id')}")
    print(f"Updated: {ts_to_str(conv.get('update_time'))}")
    print(f"Regeneration points found: {len(regen_points)}")

    if show_paths:
        paths = enumerate_paths(mapping)
        print(f"Leaf branches in tree: {len(paths)}")
        for idx, path in enumerate(paths, start=1):
            print(f"  Branch {idx}/{len(paths)}: {' -> '.join(path)}")

    for idx, point in enumerate(regen_points, start=1):
        total = point.variants[0].total
        print(f"\n  Regen point {idx}: parent={point.parent_id} ({point.parent_role}), variants={total}")
        for variant in point.variants:
            print(
                f"    {variant.index}/{variant.total} | node={variant.node_id} | created={variant.created_at}\n"
                f"      excerpt: {variant.excerpt or '(empty)'}"
            )

    return True


def main() -> None:
    args = parse_args()
    source = args.input

    if not source:
        source = pick_input_path()
        if not source:
            print("No input selected. Usage: python chatgpt_export_reader.py <path-to-export>")
            sys.exit(1)

    try:
        conversations = load_conversations_from_path(source)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(2)

    printed = 0
    for conv in conversations:
        mapping = conv.get("mapping") or {}
        if not isinstance(mapping, dict):
            continue
        if not matches_date_query(conv, mapping, args.date_query):
            continue

        if print_conversation(conv, args.show_paths):
            printed += 1
        if printed >= args.max_conversations:
            break

    if printed == 0:
        print("No conversations with regeneration points matched the filters.")


if __name__ == "__main__":
    main()
