from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.parsers.markdown_parser import (  # noqa: E402
    REQUIRED_METADATA_FIELDS,
    MarkdownParser,
)


DEFAULT_MD_PATH = (
    PROJECT_ROOT / "knowledge" / "australia" / "visa" / "mofa_entry_requirement.md"
)
REQUIRED_CONTENT_LABELS = [
    "호주 입국허가요건 원문 요약:",
    "무비자 또는 사증 관련 체류기간 정보:",
    "여권 잔여 유효기간 관련 정보:",
]


def print_result(name: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")


def check_required_metadata(metadata: dict) -> tuple[bool, str]:
    missing = sorted(REQUIRED_METADATA_FIELDS - metadata.keys())
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, ""


def check_data_sources(metadata: dict) -> tuple[bool, str]:
    data_sources = metadata.get("data_sources")
    if not isinstance(data_sources, list) or not data_sources:
        return False, "data_sources must be a non-empty list"

    has_mofa = any(
        isinstance(source, dict)
        and str(source.get("provider", "")).strip() == "외교부"
        and str(source.get("dataset", "")).strip()
        and str(source.get("url", "")).strip()
        for source in data_sources
    )

    if not has_mofa:
        return False, "외교부 provider/dataset/url entry is missing"

    return True, ""


def value_after_label(content: str, label: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith(label):
            return stripped.removeprefix(label).strip()
    return ""


def check_content_fields(content: str) -> tuple[bool, str]:
    failures = []

    for label in REQUIRED_CONTENT_LABELS:
        value = value_after_label(content, label)
        if not value:
            failures.append(f"{label} missing")
        elif value == "공식 출처 확인 필요":
            failures.append(f"{label} 공식 출처 확인 필요")

    if failures:
        return False, "; ".join(failures)

    return True, ""


def validate(md_path: Path) -> int:
    if not md_path.exists():
        print_result("file exists", False, str(md_path.relative_to(PROJECT_ROOT)))
        return 1

    print_result("file exists", True, str(md_path.relative_to(PROJECT_ROOT)))

    try:
        parsed = MarkdownParser().parse(md_path)
    except Exception as exc:
        print_result("MarkdownParser parse", False, str(exc))
        return 1

    print_result("MarkdownParser parse", True)

    metadata_ok, metadata_detail = check_required_metadata(parsed.metadata)
    print_result("required Front Matter fields", metadata_ok, metadata_detail)

    data_sources_ok, data_sources_detail = check_data_sources(parsed.metadata)
    print_result("data_sources contains 외교부", data_sources_ok, data_sources_detail)

    content_ok, content_detail = check_content_fields(parsed.content)
    print_result("main extracted content is not empty", content_ok, content_detail)

    all_passed = metadata_ok and data_sources_ok and content_ok
    print()
    print("RESULT: PASS" if all_passed else "RESULT: FAIL")
    return 0 if all_passed else 1


def main() -> int:
    md_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MD_PATH
    if not md_path.is_absolute():
        md_path = PROJECT_ROOT / md_path

    return validate(md_path)


if __name__ == "__main__":
    raise SystemExit(main())
