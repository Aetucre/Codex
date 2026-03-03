#!/usr/bin/env python3
"""Read ChatGPT export JSON and surface regeneration branches.

This utility is built for `conversations.json` files from ChatGPT exports.
It can:
- locate a conversation by date fragment (for example, 050724),
- detect regeneration points (like 1/3 in UI), and
- print the concrete branch/message IDs for each regeneration variant.
"""

from __future__ import annotations

import argparse
import json
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
        help="Path to conversations.json OR an export directory containing conversations.json",
    )
    parser.add_argument(
        "--date-query",
        default="",
        help=(
            "Date fragment to search (e.g. 050724). Matches title, update_time, "
            "create_time, and node timestamps formatted as MMDDYY."
        ),
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
        help="Also print root-to-leaf branch paths to inspect full branch structure.",
    )
    return parser.parse_args()


def resolve_conversations_file(raw_input: str) -> Path:
    path = Path(raw_input).expanduser().resolve()
    if path.is_dir():
        path = path / "conversations.json"
    if not path.exists():
        raise FileNotFoundError(f"Could not find conversations file at: {path}")
    return path


def load_conversations(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected conversations.json to be a JSON array.")
    return data


def ts_to_str(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    try:
        ts = float(value)
        return datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (TypeError, ValueError, OSError):
        return str(value)


def ts_to_mmddyy(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        ts = float(value)
        return datetime.utcfromtimestamp(ts).strftime("%m%d%y")
    except (TypeError, ValueError, OSError):
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
    roots = get_roots(mapping)
    if not roots:
        return []

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

    for root in roots:
        dfs(root, [])
    return paths


def find_regeneration_points(mapping: dict[str, dict[str, Any]]) -> list[RegenPoint]:
    points: list[RegenPoint] = []

    for parent_id, parent in mapping.items():
        child_ids = parent.get("children") or []
        if len(child_ids) < 2:
            continue

        role_groups: dict[str, list[str]] = {}
        for child_id in child_ids:
            child = mapping.get(child_id)
            if not child:
                continue
            role = node_role(child)
            role_groups.setdefault(role, []).append(child_id)

        assistant_siblings = role_groups.get("assistant", [])
        if len(assistant_siblings) < 2:
            continue

        sorted_variants = sorted(
            assistant_siblings,
            key=lambda node_id: (
                (mapping.get(node_id, {}).get("message") or {}).get("create_time")
                if (mapping.get(node_id, {}).get("message") or {}).get("create_time") is not None
                else float("inf"),
                node_id,
            ),
        )

        variants: list[RegenVariant] = []
        total = len(sorted_variants)
        for i, node_id in enumerate(sorted_variants, start=1):
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
    title = str(conv.get("title") or "").lower()
    if q in title:
        return True

    top_dates = [
        ts_to_mmddyy(conv.get("create_time")),
        ts_to_mmddyy(conv.get("update_time")),
    ]
    if any(q == d for d in top_dates if d):
        return True

    for node in mapping.values():
        created = (node.get("message") or {}).get("create_time")
        if ts_to_mmddyy(created) == q:
            return True

    return False


def print_conversation(conv: dict[str, Any], show_paths: bool) -> bool:
    mapping = conv.get("mapping") or {}
    if not mapping:
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
        all_paths = enumerate_paths(mapping)
        print(f"Leaf branches in tree: {len(all_paths)}")
        for idx, path in enumerate(all_paths, start=1):
            print(f"  Branch {idx}/{len(all_paths)}: {' -> '.join(path)}")

    for point_idx, point in enumerate(regen_points, start=1):
        total = point.variants[0].total if point.variants else 0
        print(f"\n  Regen point {point_idx}: parent={point.parent_id} ({point.parent_role}), variants={total}")
        for variant in point.variants:
            print(
                f"    {variant.index}/{variant.total} | node={variant.node_id} | "
                f"created={variant.created_at}\n"
                f"      excerpt: {variant.excerpt or '(empty)'}"
            )
    return True


def main() -> None:
    args = parse_args()
    conversations_file = resolve_conversations_file(args.input)
    conversations = load_conversations(conversations_file)

    printed = 0
    for conv in conversations:
        mapping = conv.get("mapping") or {}
        if not isinstance(mapping, dict):
            continue
        if not matches_date_query(conv, mapping, args.date_query):
            continue

        had_regens = print_conversation(conv, args.show_paths)
        if had_regens:
            printed += 1
        if printed >= args.max_conversations:
            break

    if printed == 0:
        print("No conversations with regeneration points matched the filters.")


if __name__ == "__main__":
    main()
