#!/usr/bin/env python3
"""Read ChatGPT export JSON and navigate regeneration branches.

Supports:
- conversations.json files
- export directories containing conversations.json
- .zip exports containing conversations.json

Features:
- filter conversations by date fragment (MMDDYY)
- find regeneration points (assistant sibling variants)
- interactive navigation mode for branch browsing
- export smaller JSON outputs (slim summary or per-conversation files)
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from dataclasses import asdict, dataclass
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


@dataclass
class ConversationMatch:
    conversation: dict[str, Any]
    regen_points: list[RegenPoint]


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
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open an interactive text navigator for conversation/branch browsing.",
    )
    parser.add_argument(
        "--export-slim",
        default="",
        help="Write a compact JSON report with regeneration metadata.",
    )
    parser.add_argument(
        "--export-matches-dir",
        default="",
        help="Write each matched full conversation JSON to this directory.",
    )
    return parser.parse_args()


def pick_input_path() -> str:
    import tkinter as tk
    from tkinter import filedialog

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
        possible = [n for n in names if n.endswith("conversations.json")]
        if not possible:
            raise FileNotFoundError("No conversations.json found inside the zip file.")
        chosen = possible[0]
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


def node_text(node: dict[str, Any], max_len: int = 120) -> str:
    message = node.get("message") or {}
    content = message.get("content") or {}
    parts = content.get("parts")
    if isinstance(parts, list):
        text = " ".join(str(p) for p in parts if p is not None)
    else:
        text = content.get("text") or ""
    text = " ".join(str(text).split())
    return text[:max_len] + ("…" if len(text) > max_len else "")


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


def print_conversation(conv: dict[str, Any], regen_points: list[RegenPoint], show_paths: bool) -> None:
    mapping = conv.get("mapping") or {}

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


def collect_matches(
    conversations: list[dict[str, Any]],
    date_query: str,
    max_conversations: int,
) -> list[ConversationMatch]:
    matches: list[ConversationMatch] = []
    for conv in conversations:
        mapping = conv.get("mapping") or {}
        if not isinstance(mapping, dict) or not mapping:
            continue
        if not matches_date_query(conv, mapping, date_query):
            continue

        regen_points = find_regeneration_points(mapping)
        if not regen_points:
            continue

        matches.append(ConversationMatch(conv, regen_points))
        if len(matches) >= max_conversations:
            break
    return matches


def sanitize_filename(value: str) -> str:
    safe = "".join(c if c.isalnum() or c in {"-", "_", " "} else "_" for c in value.strip())
    safe = "_".join(safe.split())
    return safe[:80] or "untitled"


def export_slim(path: Path, matches: list[ConversationMatch]) -> None:
    payload = []
    for entry in matches:
        conv = entry.conversation
        payload.append(
            {
                "id": conv.get("id"),
                "title": conv.get("title"),
                "create_time": conv.get("create_time"),
                "update_time": conv.get("update_time"),
                "regen_points": [
                    {
                        "parent_id": rp.parent_id,
                        "parent_role": rp.parent_role,
                        "variants": [asdict(v) for v in rp.variants],
                    }
                    for rp in entry.regen_points
                ],
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def export_matches_dir(directory: Path, matches: list[ConversationMatch]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for idx, entry in enumerate(matches, start=1):
        conv = entry.conversation
        title = sanitize_filename(str(conv.get("title") or "untitled"))
        conv_id = str(conv.get("id") or f"conversation_{idx}")
        out = directory / f"{idx:03d}_{title}_{conv_id}.json"
        out.write_text(json.dumps(conv, indent=2, ensure_ascii=False), encoding="utf-8")


def run_interactive(matches: list[ConversationMatch], show_paths: bool) -> None:
    if not matches:
        print("No matches to browse.")
        return

    print("\nInteractive mode. Commands:")
    print("  list                 - list matched conversations")
    print("  open <n>             - show conversation summary")
    print("  regen <n> <m>        - show all variants for regen point m in conversation n")
    print("  variant <n> <m> <k>  - show a specific variant k from regen point m in conversation n")
    print("  q                    - quit")

    def list_conversations() -> None:
        for i, entry in enumerate(matches, start=1):
            conv = entry.conversation
            print(
                f"{i:>3}. {conv.get('title') or '(untitled)'} "
                f"| regens={len(entry.regen_points)} | updated={ts_to_str(conv.get('update_time'))}"
            )

    list_conversations()

    while True:
        try:
            raw = input("\nreader> ").strip()
        except EOFError:
            print()
            return

        if not raw:
            continue
        if raw in {"q", "quit", "exit"}:
            return
        if raw == "list":
            list_conversations()
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        if cmd == "open" and len(parts) == 2 and parts[1].isdigit():
            ci = int(parts[1]) - 1
            if not (0 <= ci < len(matches)):
                print("Invalid conversation index.")
                continue
            entry = matches[ci]
            print_conversation(entry.conversation, entry.regen_points, show_paths)
            continue

        if cmd == "regen" and len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
            ci = int(parts[1]) - 1
            ri = int(parts[2]) - 1
            if not (0 <= ci < len(matches)):
                print("Invalid conversation index.")
                continue
            entry = matches[ci]
            if not (0 <= ri < len(entry.regen_points)):
                print("Invalid regen point index.")
                continue
            point = entry.regen_points[ri]
            print(f"Regen point {ri + 1} of conversation {ci + 1}: parent={point.parent_id}")
            for variant in point.variants:
                print(
                    f"  {variant.index}/{variant.total} | node={variant.node_id} | created={variant.created_at}\n"
                    f"    {variant.excerpt}"
                )
            continue

        if (
            cmd == "variant"
            and len(parts) == 4
            and parts[1].isdigit()
            and parts[2].isdigit()
            and parts[3].isdigit()
        ):
            ci = int(parts[1]) - 1
            ri = int(parts[2]) - 1
            vi = int(parts[3]) - 1
            if not (0 <= ci < len(matches)):
                print("Invalid conversation index.")
                continue
            entry = matches[ci]
            if not (0 <= ri < len(entry.regen_points)):
                print("Invalid regen point index.")
                continue
            point = entry.regen_points[ri]
            if not (0 <= vi < len(point.variants)):
                print("Invalid variant index.")
                continue
            variant = point.variants[vi]
            print(
                f"Conversation {ci + 1}, regen {ri + 1}, variant {variant.index}/{variant.total}\n"
                f"Node: {variant.node_id}\n"
                f"Created: {variant.created_at}\n"
                f"Excerpt: {variant.excerpt or '(empty)'}"
            )
            continue

        print("Unknown command. Try: list, open <n>, regen <n> <m>, variant <n> <m> <k>, q")


def main() -> None:
    args = parse_args()
    source = args.input

    if not source:
        try:
            source = pick_input_path()
        except Exception:
            source = ""
        if not source:
            print("No input selected. Usage: python chatgpt_export_reader.py <path-to-export>")
            sys.exit(1)

    try:
        conversations = load_conversations_from_path(source)
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(2)

    matches = collect_matches(conversations, args.date_query, args.max_conversations)

    if args.export_slim:
        export_slim(Path(args.export_slim), matches)
        print(f"Wrote slim report: {args.export_slim}")

    if args.export_matches_dir:
        export_matches_dir(Path(args.export_matches_dir), matches)
        print(f"Wrote matched conversation files to: {args.export_matches_dir}")

    if not matches:
        print("No conversations with regeneration points matched the filters.")
        return

    use_interactive = args.interactive or sys.stdin.isatty()
    if use_interactive:
        run_interactive(matches, args.show_paths)
        return

    for entry in matches:
        print_conversation(entry.conversation, entry.regen_points, args.show_paths)


if __name__ == "__main__":
    main()
