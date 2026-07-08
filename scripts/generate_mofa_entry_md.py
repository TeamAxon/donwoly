from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))


DEFAULT_SOURCE_URL = "https://www.data.go.kr/"
DEFAULT_OUTPUT_PATH = (
    PROJECT_ROOT / "knowledge" / "australia" / "visa" / "mofa_entry_requirement.md"
)
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"


FIELD_ALIASES = {
    "country": [
        "country",
        "country_name",
        "country_nm",
        "국가",
        "국가명",
        "국가_지역명",
        "국가·지역명",
        "국가및지역명",
        "한글국가명",
    ],
    "country_code": [
        "country_code",
        "iso_code",
        "iso2",
        "국가코드",
        "iso국가코드",
    ],
    "entry_requirement": [
        "entry_requirement",
        "visa_requirement",
        "입국허가요건",
        "입국요건",
        "사증",
        "비자",
        "비자요건",
        "사증요건",
    ],
    "visa_free_stay": [
        "visa_free_stay",
        "stay_period",
        "무비자체류기간",
        "무사증체류기간",
        "체류기간",
    ],
    "passport_validity": [
        "passport_validity",
        "여권잔여유효기간",
        "여권유효기간",
    ],
    "purpose": [
        "purpose",
        "visit_purpose",
        "방문목적",
        "입국목적",
    ],
    "note": [
        "note",
        "notes",
        "remark",
        "remarks",
        "비고",
        "유의사항",
        "참고사항",
    ],
    "updated_at": [
        "updated_at",
        "update_date",
        "modified_at",
        "수정일",
        "갱신일",
        "업데이트일",
        "기준일",
    ],
}


def normalize_column_name(name: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", name.lower())


def build_column_mapping(row: dict[str, Any]) -> dict[str, str]:
    """Map unpredictable public-data column names to stable internal fields."""

    normalized_columns = {
        normalize_column_name(column): column
        for column in row.keys()
    }

    mapping: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_column_name(alias)
            if normalized_alias in normalized_columns:
                mapping[field] = normalized_columns[normalized_alias]
                break

    return mapping


def read_input_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        return read_csv(path)
    if path.suffix.lower() == ".json":
        return read_json(path)

    raise ValueError(f"지원하지 않는 파일 형식입니다: {path.suffix}")


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_json(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = extract_json_rows(data)

    if not all(isinstance(row, dict) for row in rows):
        raise ValueError("JSON 데이터는 객체 목록 형태여야 합니다.")

    return rows


def extract_json_rows(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data

    if not isinstance(data, dict):
        raise ValueError("JSON 최상위 데이터는 list 또는 dict여야 합니다.")

    for key in ("data", "items", "records", "rows"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    response_items = (
        data.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item")
    )
    if isinstance(response_items, list):
        return response_items
    if isinstance(response_items, dict):
        return [response_items]

    raise ValueError("JSON 안에서 데이터 row 목록을 찾지 못했습니다.")


def find_default_input_file() -> Path:
    candidates = sorted(
        [
            *RAW_DATA_DIR.glob("*.csv"),
            *RAW_DATA_DIR.glob("*.json"),
        ]
    )

    if not candidates:
        raise FileNotFoundError(
            "data/raw/ 폴더에 CSV 또는 JSON 원본 파일이 없습니다. "
            "예: data/raw/mofa_entry_requirement.csv"
        )

    return candidates[0]


def get_value(row: dict[str, Any], mapping: dict[str, str], field: str) -> str:
    column = mapping.get(field)
    if not column:
        return ""

    value = row.get(column, "")
    if value is None:
        return ""

    return str(value).strip()


def is_australia_row(row: dict[str, Any], mapping: dict[str, str]) -> bool:
    country = get_value(row, mapping, "country").lower()
    country_code = get_value(row, mapping, "country_code").upper()

    return (
        "호주" in country
        or "australia" in country
        or country_code in {"AU", "AUS"}
    )


def extract_australia_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not rows:
        raise ValueError("원본 데이터에 row가 없습니다.")

    mapping = build_column_mapping(rows[0])
    if not mapping.get("country") and not mapping.get("country_code"):
        raise ValueError("호주 row를 찾기 위한 국가명 또는 국가코드 컬럼이 필요합니다.")

    australia_rows = [row for row in rows if is_australia_row(row, mapping)]
    if not australia_rows:
        raise ValueError("호주 관련 row를 찾지 못했습니다.")

    return australia_rows, mapping


def render_frontmatter(source_url: str, last_updated: str) -> str:
    metadata = {
        "country": "호주",
        "country_code": "AU",
        "target_user": "워킹홀리데이",
        "category": "visa",
        "section": "entry_requirement",
        "title": "호주 입국허가요건",
        "chunk_id": "visa_mofa_entry_requirement",
        "source": source_url,
        "data_sources": [
            {
                "provider": "외교부",
                "dataset": "국가·지역별 입국허가요건",
                "url": source_url,
            }
        ],
        "language": "ko",
        "last_updated": last_updated,
    }

    return yaml.safe_dump(
        metadata,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()


def render_row_summary(row: dict[str, Any], mapping: dict[str, str], index: int) -> str:
    entry_requirement = get_value(row, mapping, "entry_requirement")
    visa_free_stay = get_value(row, mapping, "visa_free_stay")
    passport_validity = get_value(row, mapping, "passport_validity")
    purpose = get_value(row, mapping, "purpose")
    note = get_value(row, mapping, "note")
    updated_at = get_value(row, mapping, "updated_at")

    lines = []
    if index > 1:
        lines.append(f"## 원본 데이터 항목 {index}")

    lines.extend(
        [
            "호주 입국허가요건은 외교부 공공데이터 '국가·지역별 입국허가요건'을 기준으로 확인한다.",
            "워킹홀리데이 사용자는 호주 출국 전 입국 가능 여부, 비자 필요 여부, 체류 가능 조건을 공식 출처에서 확인해야 한다.",
        ]
    )

    if entry_requirement:
        lines.append(f"호주 입국허가요건 원문 요약: {entry_requirement}")
    else:
        lines.append("호주 입국허가요건 원문 요약: 공식 출처 확인 필요")

    if visa_free_stay:
        lines.append(f"무비자 또는 사증 관련 체류기간 정보: {visa_free_stay}")
    else:
        lines.append("무비자 또는 사증 관련 체류기간 정보: 공식 출처 확인 필요")

    if passport_validity:
        lines.append(f"여권 잔여 유효기간 관련 정보: {passport_validity}")
    else:
        lines.append("여권 잔여 유효기간 관련 정보: 공식 출처 확인 필요")

    if purpose:
        lines.append(f"적용 가능한 방문 목적: {purpose}")

    if note:
        lines.append(f"유의사항: {note}")

    if updated_at:
        lines.append(f"원본 데이터 기준일 또는 수정일: {updated_at}")

    lines.extend(
        [
            "417 워킹홀리데이 비자 신청 가능 여부와 실제 비자 조건은 호주 Department of Home Affairs 공식 안내에서 별도로 확인해야 한다.",
            "첫달가이드는 외교부 공공데이터 및 공식 출처 기준으로 정보를 요약하지만, 비자 최종 판단을 대신하지 않는다.",
        ]
    )

    return "\n\n".join(lines)


def render_markdown(rows: list[dict[str, Any]], mapping: dict[str, str], source_url: str, last_updated: str) -> str:
    frontmatter = render_frontmatter(source_url=source_url, last_updated=last_updated)
    body_sections = [
        "# 호주 입국허가요건",
        *[
            render_row_summary(row=row, mapping=mapping, index=index)
            for index, row in enumerate(rows, start=1)
        ],
        "## 자주 묻는 질문",
        "- 호주 입국 전 비자가 필요한가?",
        "- 호주 입국허가요건은 어디에서 확인해야 하는가?",
        "- 워킹홀리데이 비자와 일반 입국요건은 어떻게 구분해야 하는가?",
        "- 여권 유효기간이나 체류기간 조건은 어디에서 확인해야 하는가?",
        "- 첫달가이드의 입국요건 답변은 최종 비자 판단인가?",
    ]

    return f"---\n{frontmatter}\n---\n\n" + "\n\n".join(body_sections) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Markdown Knowledge from MOFA entry requirement CSV/JSON."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="CSV or JSON file path. Default: first .csv/.json file under data/raw/.",
    )
    parser.add_argument(
        "--source-url",
        default=DEFAULT_SOURCE_URL,
        help="Official source URL for Front Matter source and data_sources.",
    )
    parser.add_argument(
        "--last-updated",
        default="2026-07-07",
        help="last_updated value for generated Markdown.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help="Output Markdown path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    input_path = Path(args.input_file) if args.input_file else find_default_input_file()
    if not input_path.is_absolute():
        input_path = PROJECT_ROOT / input_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    try:
        rows = read_input_file(input_path)
        australia_rows, mapping = extract_australia_rows(rows)
        markdown = render_markdown(
            rows=australia_rows,
            mapping=mapping,
            source_url=args.source_url,
            last_updated=args.last_updated,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
    except Exception as exc:
        print("[error]")
        print(exc)
        return 1

    print(f"Input file: {input_path.relative_to(PROJECT_ROOT)}")
    print(f"Australia rows: {len(australia_rows)}")
    print(f"Column mapping: {mapping}")
    print(f"Generated markdown: {output_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
