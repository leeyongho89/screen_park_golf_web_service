from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import ZipFile

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent if (BACKEND_DIR.parent / "db").exists() else BACKEND_DIR
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import models, services  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.utils import normalize_phone  # noqa: E402


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "office_rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "package_rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

NAME_HEADERS = {"이름", "방문자", "수강생"}
PHONE_HEADERS = {"전화번호", "연락처"}
EXCLUDED_NAMES = {"수유리", "하이별", "여대생", "유클", "구슬동자", "백마"}
WORDLIKE_NAMES = {"등산", "정기회원", "중복표시", "번호", "이름", "방문자", "수강생", "연락처", "전화번호"}


@dataclass(frozen=True)
class MemberCandidate:
    name: str
    phone: str
    source_file: str
    source_sheet: str
    source_row: int


@dataclass
class ImportPlan:
    candidates: list[MemberCandidate] = field(default_factory=list)
    conflicts: dict[str, list[MemberCandidate]] = field(default_factory=dict)
    skipped_no_phone: int = 0
    skipped_excluded: int = 0
    skipped_wordlike: int = 0
    sheets_without_headers: int = 0


def read_shared_strings(workbook: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
    strings = []
    for item in root.findall("main:si", NS):
        strings.append("".join(text.text or "" for text in item.findall(".//main:t", NS)))
    return strings


def column_index(cell_ref: str) -> int:
    letters = "".join(char for char in cell_ref if char.isalpha()) or "A"
    value = 0
    for char in letters:
        value = value * 26 + ord(char.upper()) - 64
    return value - 1


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//main:t", NS)).strip()
    value = cell.find("main:v", NS)
    if value is None:
        return ""
    raw_value = (value.text or "").strip()
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(raw_value)].strip()
        except (IndexError, ValueError):
            return raw_value
    return raw_value


def workbook_sheets(workbook: ZipFile) -> list[tuple[str, str]]:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root.findall("package_rel:Relationship", NS)}
    sheets = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
        rel_id = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rels.get(rel_id or "", "")
        path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
        sheets.append((sheet.attrib.get("name", "Sheet"), path))
    return sheets


def sheet_rows(workbook: ZipFile, sheet_path: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(workbook.read(sheet_path))
    rows = []
    for row in root.findall("main:sheetData/main:row", NS):
        cells: dict[int, str] = {}
        max_index = -1
        for cell in row.findall("main:c", NS):
            index = column_index(cell.attrib.get("r", "A"))
            cells[index] = cell_value(cell, shared_strings)
            max_index = max(max_index, index)
        rows.append([cells.get(index, "") for index in range(max_index + 1)])
    return rows


def find_name_phone_columns(rows: list[list[str]]) -> tuple[int, int, int] | None:
    for row_index, row in enumerate(rows[:30]):
        normalized = [str(value).strip() for value in row]
        name_columns = [index for index, value in enumerate(normalized) if value in NAME_HEADERS]
        phone_columns = [index for index, value in enumerate(normalized) if value in PHONE_HEADERS]
        if name_columns and phone_columns:
            return row_index, name_columns[0], phone_columns[0]
    return None


def is_wordlike_name(name: str) -> bool:
    if not name or len(name) < 2:
        return True
    if name in WORDLIKE_NAMES:
        return True
    return name.isdigit()


def collect_candidates(raw_dir: Path) -> ImportPlan:
    plan = ImportPlan()
    raw_candidates: list[MemberCandidate] = []
    for path in sorted(raw_dir.glob("*.xlsx")):
        with ZipFile(path) as workbook:
            shared_strings = read_shared_strings(workbook)
            for sheet_name, sheet_path in workbook_sheets(workbook):
                if sheet_path not in workbook.namelist():
                    plan.sheets_without_headers += 1
                    continue
                rows = sheet_rows(workbook, sheet_path, shared_strings)
                header = find_name_phone_columns(rows)
                if header is None:
                    plan.sheets_without_headers += 1
                    continue
                header_row, name_column, phone_column = header
                for row_number, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
                    name = str(row[name_column]).strip() if name_column < len(row) else ""
                    phone = normalize_phone(row[phone_column] if phone_column < len(row) else "")
                    if not name and not phone:
                        continue
                    if name in EXCLUDED_NAMES:
                        plan.skipped_excluded += 1
                        continue
                    if is_wordlike_name(name):
                        plan.skipped_wordlike += 1
                        continue
                    if not phone or len(phone) < 8:
                        plan.skipped_no_phone += 1
                        continue
                    raw_candidates.append(
                        MemberCandidate(
                            name=name,
                            phone=phone,
                            source_file=path.name,
                            source_sheet=sheet_name,
                            source_row=row_number,
                        )
                    )

    by_phone: dict[str, list[MemberCandidate]] = defaultdict(list)
    for candidate in raw_candidates:
        by_phone[candidate.phone].append(candidate)

    for phone, phone_candidates in sorted(by_phone.items()):
        names = {candidate.name for candidate in phone_candidates}
        if len(names) > 1:
            plan.conflicts[phone] = phone_candidates
        else:
            plan.candidates.append(phone_candidates[0])
    return plan


def apply_plan(plan: ImportPlan) -> tuple[int, int]:
    created = 0
    skipped_existing = 0
    with SessionLocal() as db:
        for candidate in plan.candidates:
            existing = services.get_active_member_by_phone(db, candidate.phone)
            if existing:
                skipped_existing += 1
                continue
            member = models.Member(
                name=candidate.name,
                phone=candidate.phone,
                sms_agree=True,
                memo=f"엑셀 회원 이관: {candidate.source_file} / {candidate.source_sheet} / {candidate.source_row}행",
            )
            db.add(member)
            db.flush()
            services.add_audit_log(
                db,
                action_type="회원 엑셀 이관",
                target_type="member",
                target_id=member.id,
                after_data=services.model_snapshot(member, ["id", "name", "phone", "sms_agree", "is_active"]),
            )
            created += 1
        db.commit()
    return created, skipped_existing


def print_plan(plan: ImportPlan, applied: bool = False, created: int = 0, skipped_existing: int = 0) -> None:
    print(f"등록 후보: {len(plan.candidates)}명")
    print(f"이름 충돌 전화번호: {len(plan.conflicts)}건")
    print(f"전화번호 없음/오류 스킵: {plan.skipped_no_phone}행")
    print(f"제외 이름 스킵: {plan.skipped_excluded}행")
    print(f"일반 단어/헤더 스킵: {plan.skipped_wordlike}행")
    print(f"헤더 미인식 시트: {plan.sheets_without_headers}개")
    if applied:
        print(f"신규 등록: {created}명")
        print(f"기존 회원 스킵: {skipped_existing}명")
    else:
        print("dry-run입니다. 실제 등록하려면 --apply를 붙여 실행하세요.")
    if plan.conflicts:
        print("충돌 목록:")
        for phone, candidates in plan.conflicts.items():
            names = ", ".join(sorted({candidate.name for candidate in candidates}))
            sources = "; ".join(
                f"{candidate.source_file}/{candidate.source_sheet}/{candidate.source_row}행" for candidate in candidates[:4]
            )
            print(f"- {phone}: {names} ({sources})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="db/raw/raw_data 엑셀 파일에서 회원 이름과 전화번호만 이관합니다.")
    parser.add_argument("--raw-dir", type=Path, default=ROOT_DIR / "db" / "raw" / "raw_data")
    parser.add_argument("--apply", action="store_true", help="dry-run이 아니라 실제 DB에 회원을 등록합니다.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    plan = collect_candidates(args.raw_dir)
    created = 0
    skipped_existing = 0
    if args.apply:
        created, skipped_existing = apply_plan(plan)
    print_plan(plan, applied=args.apply, created=created, skipped_existing=skipped_existing)


if __name__ == "__main__":
    main()
