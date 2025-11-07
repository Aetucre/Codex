#!/usr/bin/env python3
"""Convert ChatGPT Markdown logs into structured exchange blocks."""
from __future__ import annotations

import argparse
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class BranchResponse:
    """Represents a single branch response attached to a prompt."""

    index: int
    content: str

    @property
    def response_id_suffix(self) -> str:
        """Return the suffix for the branch response identifier."""
        return f"b{self.index}"


@dataclass
class PromptBlock:
    """Container for a prompt, its branches, and mainline response."""

    prompt_text: str
    branches: List[BranchResponse]
    mainline: Optional[str]


def parse_markdown_chat(content: str) -> List[PromptBlock]:
    """Parse exported ChatGPT Markdown logs into prompt blocks.

    Each block starts with "# You said:" followed by optional "## Branch ChatGPT said:"
    sections and an optional "# ChatGPT said:" section.
    """

    lines = content.splitlines()
    blocks: List[PromptBlock] = []
    i = 0
    total_lines = len(lines)

    def collect_until(start_index: int, stop_tokens: tuple[str, ...]) -> tuple[str, int]:
        collected: List[str] = []
        index = start_index
        while index < total_lines:
            raw = lines[index]
            stripped = raw.lstrip()
            if stripped.startswith(stop_tokens):
                break
            collected.append(raw)
            index += 1
        # Trim trailing blank lines for cleanliness
        while collected and collected[-1].strip() == "":
            collected.pop()
        while collected and collected[0].strip() == "":
            collected.pop(0)
        return "\n".join(collected), index

    while i < total_lines:
        line = lines[i]
        stripped = line.lstrip()
        if not stripped.startswith("# You said:"):
            i += 1
            continue

        # Collect prompt text
        prompt_text, next_index = collect_until(
            i + 1,
            ("## Branch ChatGPT said:", "# ChatGPT said:", "# You said:"),
        )

        branches: List[BranchResponse] = []
        branch_counter = 0
        i = next_index

        # Gather branches if any
        while i < total_lines and lines[i].lstrip().startswith("## Branch ChatGPT said:"):
            branch_counter += 1
            branch_text, new_index = collect_until(
                i + 1,
                ("## Branch ChatGPT said:", "# ChatGPT said:", "# You said:"),
            )
            branches.append(BranchResponse(index=branch_counter, content=branch_text))
            i = new_index

        # Collect mainline response if present
        mainline_content: Optional[str] = None
        if i < total_lines and lines[i].lstrip().startswith("# ChatGPT said:"):
            mainline_content, i = collect_until(i + 1, ("# You said:",))
        blocks.append(PromptBlock(prompt_text=prompt_text, branches=branches, mainline=mainline_content))

    return blocks


def build_exchange_block(
    block_index: int,
    prompt_block: PromptBlock,
    chat_id: str,
    scene: str,
    timestamp: str,
) -> str:
    """Construct the formatted exchange block string."""

    meta_id = f"{chat_id}-PR{block_index:03d}"
    prompt_id = f"{chat_id}-Prompt{block_index:03d}"
    response_prefix = f"{chat_id}-Response{block_index:03d}"
    branch_type = "multi" if len(prompt_block.branches) > 1 else "single"

    lines: List[str] = ["```exchange", "meta:"]
    lines.append(f"  id: {meta_id}")
    lines.append(f"  scene: {scene}")
    lines.append(f"  branch_type: {branch_type}")
    lines.append(f"  prompt_id: {prompt_id}")
    lines.append(f"  created: {timestamp}")
    lines.append("content:")
    lines.append("  # You said:")

    if prompt_block.prompt_text:
        for prompt_line in prompt_block.prompt_text.splitlines():
            lines.append(f"  {prompt_line}")
    else:
        lines.append("  ")
    lines.append(f"  ^{prompt_id}")

    if prompt_block.branches:
        lines.append("  ")
        lines.append("  ## Branches")
        for branch in prompt_block.branches:
            lines.append("  ")
            lines.append(f"  ### Branch {branch.index} – ChatGPT said:")
            if branch.content:
                for branch_line in branch.content.splitlines():
                    lines.append(f"  {branch_line}")
            else:
                lines.append("  ")
            lines.append(f"  ^{response_prefix}-{branch.response_id_suffix}")

    if prompt_block.mainline is not None:
        if prompt_block.branches:
            lines.append("  ")
        else:
            lines.append("  ")
        lines.append("  ### Mainline – ChatGPT said:")
        if prompt_block.mainline:
            for main_line in prompt_block.mainline.splitlines():
                lines.append(f"  {main_line}")
        else:
            lines.append("  ")
        lines.append(f"  ^{response_prefix}-main")

    lines.append("```")
    lines.append(f"^{meta_id}")
    return "\n".join(lines)


def determine_output_path(args: argparse.Namespace) -> Optional[Path]:
    """Figure out where the rendered output should be written."""

    if args.in_place and args.output:
        raise SystemExit("--in-place cannot be combined with --output")
    if args.in_place and args.append:
        raise SystemExit("--in-place cannot be combined with --append")
    if args.append and not args.output:
        raise SystemExit("--append requires --output to be specified")

    if args.in_place:
        return Path(args.input)
    if args.output:
        return Path(args.output)
    return None


def write_output(output_path: Optional[Path], blocks: List[str], append: bool) -> None:
    """Write the exchange blocks to a file or stdout."""

    rendered = "\n\n".join(blocks)

    if output_path is None:
        print(rendered)
        return

    mode = "a" if append else "w"
    file_exists = output_path.exists()
    with output_path.open(mode, encoding="utf-8") as file:
        if append and file_exists and output_path.stat().st_size > 0:
            file.write("\n\n")
        file.write(rendered)
        file.write("\n")


def build_cli_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the command-line interface."""

    description = (
        "Convert ChatGPT Markdown transcripts into fenced exchange blocks suitable "
        "for Obsidian."
    )
    examples = (
        "examples:\n"
        "  make_exchanges.py chat.md\n"
        "  make_exchanges.py chat.md --output exchanges.md --scene 'Morning routine'\n"
        "  make_exchanges.py chat.md --chat-id CustomChat --in-place\n"
    )

    parser = argparse.ArgumentParser(
        description=description,
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="Path to the exported ChatGPT Markdown file")
    parser.add_argument(
        "--output", "-o", help="Destination Markdown file for the exchange blocks"
    )
    parser.add_argument(
        "--chat-id",
        help="Override the chat identifier (defaults to input filename stem)",
    )
    parser.add_argument(
        "--scene",
        default="Untitled scene",
        help="Scene description to place in the meta section",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the input file with the generated exchange blocks",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append the generated blocks to the output file",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> None:
    """Program entry point."""

    parser = build_cli_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")

    output_path = determine_output_path(args)

    chat_id = args.chat_id or input_path.stem
    timestamp = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()

    text = input_path.read_text(encoding="utf-8")
    prompt_blocks = parse_markdown_chat(text)

    if not prompt_blocks:
        raise SystemExit("No prompts found in the input file.")

    rendered_blocks = [
        build_exchange_block(index + 1, block, chat_id, args.scene, timestamp)
        for index, block in enumerate(prompt_blocks)
    ]

    write_output(output_path, rendered_blocks, args.append)


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    main()
