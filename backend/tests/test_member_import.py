from zipfile import ZipFile

from scripts.import_members_from_raw import collect_candidates


def write_inline_xlsx(path, rows):
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row):
            column = chr(ord("A") + column_index)
            cells.append(
                f'<c r="{column}{row_index}" t="inlineStr"><is><t>{value}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    with ZipFile(path, "w") as workbook:
        workbook.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="연락처" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        workbook.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        workbook.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>""",
        )


def test_collect_candidates_deduplicates_excludes_and_reports_name_conflicts(tmp_path):
    write_inline_xlsx(
        tmp_path / "members.xlsx",
        [
            ["이름", "전화번호", "비고"],
            ["홍길동", "010-1111-2222", ""],
            ["홍길동", "01011112222", "중복"],
            ["수유리", "010-3333-4444", "제외"],
            ["등산", "010-5555-6666", "일반 단어"],
            ["전화없음", "", ""],
            ["김철수", "010-7777-8888", ""],
            ["김철민", "01077778888", "이름 충돌"],
        ],
    )

    plan = collect_candidates(tmp_path)

    assert [(candidate.name, candidate.phone) for candidate in plan.candidates] == [("홍길동", "01011112222")]
    assert sorted(plan.conflicts.keys()) == ["01077778888"]
    assert plan.skipped_excluded == 1
    assert plan.skipped_wordlike == 1
    assert plan.skipped_no_phone == 1
