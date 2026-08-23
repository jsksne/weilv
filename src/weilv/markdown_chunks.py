"""Generate review candidates from Markdown without breaking paragraphs."""

import argparse
import json
import re
import sys
from pathlib import Path

_ATX_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_BOLD_HEADING = re.compile(r"^\s*\*\*(.+?)\*\*\s*$")


def chunk_markdown(
    markdown: str,
    source_path: str,
    min_chars: int = 400,
    max_chars: int = 900,
) -> list[dict]:
    """Group Markdown paragraphs by section and retain their source line range."""

    paragraphs: list[tuple[list[str], str, int, int]] = []
    section_path: list[str] = []
    paragraph_lines: list[str] = []
    paragraph_start = 0

    def flush_paragraph(end_line: int) -> None:
        nonlocal paragraph_lines, paragraph_start
        if paragraph_lines:
            paragraphs.append(
                (section_path.copy(), "\n".join(paragraph_lines).strip(), paragraph_start, end_line)
            )
            paragraph_lines = []
            paragraph_start = 0

    for line_number, line in enumerate(markdown.splitlines(), start=1):
        line = line.replace("\u00a0", " ")
        heading = _ATX_HEADING.match(line)
        bold_heading = _BOLD_HEADING.match(line) if not heading else None
        if heading or bold_heading:
            flush_paragraph(line_number - 1)
            level = len(heading.group(1)) if heading else 2
            title = (heading.group(2) if heading else bold_heading.group(1)).strip()
            section_path = [*section_path[: level - 1], title]
            continue

        if not line.strip():
            flush_paragraph(line_number - 1)
            continue

        if not paragraph_lines:
            paragraph_start = line_number
        paragraph_lines.append(line.strip())

    flush_paragraph(len(markdown.splitlines()))

    chunks: list[dict] = []
    current_path: list[str] = []
    current_parts: list[str] = []
    current_start = 0
    current_end = 0

    def flush_chunk() -> None:
        nonlocal current_parts, current_start, current_end
        if current_parts:
            chunks.append(
                {
                    "section_path": current_path.copy(),
                    "content": "\n\n".join(current_parts),
                    "source_locator": f"{source_path}:L{current_start}-L{current_end}",
                }
            )
            current_parts = []
            current_start = 0
            current_end = 0

    for path, content, start_line, end_line in paragraphs:
        joined_length = len("\n\n".join([*current_parts, content]))
        if current_parts and (
            path != current_path
            or (joined_length > max_chars and len("\n\n".join(current_parts)) >= min_chars)
        ):
            flush_chunk()

        if not current_parts:
            current_path = path
            current_start = start_line
        current_parts.append(content)
        current_end = end_line

    flush_chunk()
    return chunks


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Generate review candidates from Markdown")
    parser.add_argument("source", type=Path)
    parser.add_argument("--min-chars", type=int, default=400)
    parser.add_argument("--max-chars", type=int, default=900)
    args = parser.parse_args()

    chunks = chunk_markdown(
        args.source.read_text(encoding="utf-8"),
        source_path=args.source.as_posix(),
        min_chars=args.min_chars,
        max_chars=args.max_chars,
    )
    for chunk in chunks:
        print(json.dumps(chunk, ensure_ascii=False))


if __name__ == "__main__":
    main()
