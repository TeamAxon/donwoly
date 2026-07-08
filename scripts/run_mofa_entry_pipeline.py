from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
GENERATED_MD_PATH = (
    PROJECT_ROOT / "knowledge" / "australia" / "visa" / "mofa_entry_requirement.md"
)


def find_raw_file() -> Path:
    candidates = sorted(
        [
            *RAW_DATA_DIR.glob("*.csv"),
            *RAW_DATA_DIR.glob("*.json"),
        ]
    )

    if not candidates:
        raise FileNotFoundError(
            "data/raw/ 폴더에 외교부 원본 CSV 또는 JSON 파일이 없습니다.\n"
            "예: data/raw/mofa_entry_requirement.csv 또는 "
            "data/raw/mofa_entry_requirement.json"
        )

    return candidates[0]


def print_step(step: str) -> None:
    print()
    print("=" * 72, flush=True)
    print(step, flush=True)
    print("=" * 72, flush=True)


def run_command(command: list[str]) -> None:
    print("$ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        raise RuntimeError(f"명령 실행 실패: {' '.join(command)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MOFA entry requirement Markdown generation pipeline."
    )
    parser.add_argument(
        "--input",
        help="CSV or JSON file path. Default: first .csv/.json file under data/raw/.",
    )
    parser.add_argument(
        "--source-url",
        default="https://www.data.go.kr/",
        help="Official source URL for generated Markdown.",
    )
    parser.add_argument(
        "--last-updated",
        default="2026-07-07",
        help="last_updated value for generated Markdown.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        print_step("1. 원본 데이터 파일 탐색")
        input_file = Path(args.input) if args.input else find_raw_file()
        if not input_file.is_absolute():
            input_file = PROJECT_ROOT / input_file
        if not input_file.exists():
            raise FileNotFoundError(f"원본 파일이 없습니다: {input_file}")
        print(f"Raw file: {input_file.relative_to(PROJECT_ROOT)}")

        print_step("2. 외교부 원본 데이터 -> Markdown 생성")
        run_command(
            [
                sys.executable,
                "scripts/generate_mofa_entry_md.py",
                str(input_file.relative_to(PROJECT_ROOT)),
                "--source-url",
                args.source_url,
                "--last-updated",
                args.last_updated,
            ]
        )

        print_step("3. 생성된 Markdown 파일 확인")
        if not GENERATED_MD_PATH.exists():
            raise FileNotFoundError(
                f"Markdown 생성 실패: {GENERATED_MD_PATH.relative_to(PROJECT_ROOT)}"
            )
        print(f"Generated: {GENERATED_MD_PATH.relative_to(PROJECT_ROOT)}")

        print_step("4. 생성 Markdown 품질 검증")
        run_command(
            [
                sys.executable,
                "scripts/validate_generated_md.py",
                str(GENERATED_MD_PATH.relative_to(PROJECT_ROOT)),
            ]
        )

        print_step("5. ingest_all dry-run")
        run_command(
            [
                sys.executable,
                "scripts/ingest_all_md.py",
                "knowledge/australia",
                "--dry-run",
            ]
        )

    except Exception as exc:
        print()
        print("[FAIL]")
        print(exc)
        return 1

    print()
    print("[PASS] MOFA entry requirement pipeline completed.")
    print("Qdrant 적재는 실행하지 않았습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
