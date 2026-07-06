from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.parsers.markdown_parser import MarkdownParser  # noqa: E402


def print_preview(text: str, max_chars: int = 220) -> None:
    preview = text.strip()
    if len(preview) > max_chars:
        preview = preview[:max_chars].rstrip() + "..."
    print(preview)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python scripts/parse_markdown.py <markdown-file-path>")
        return 1

    path = Path(sys.argv[1])
    parser = MarkdownParser()

    try:
        parsed = parser.parse(path)
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print("[metadata]")
    for key, value in parsed.metadata.items():
        print(f"{key}: {value}")

    print()
    print("[source_path]")
    print(parsed.source_path)

    print()
    print("[content preview]")
    print_preview(parsed.content)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
