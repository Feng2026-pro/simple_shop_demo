#!/usr/bin/env python3
"""
Convert runner cases JSON to 2-sheet Excel.

Sheets:
1) dependencies
2) cases (steps/db_assert embedded in JSON columns)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import Workbook

DEPENDENCY_COLUMNS = [
    "name",
    "depends_on",
    "method",
    "path",
    "headers_json",
    "body_json",
    "assert_status",
    "assert_checks",
    "extract_json",
]

CASE_COLUMNS = [
    "id",
    "name",
    "enabled",
    "case_assert_status",
    "case_assert_checks",
    "steps_json",
    "db_assert_json",
]


def _compact_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_plan(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Cases JSON root must be object")
    deps = raw.get("dependencies") or []
    cases = raw.get("cases") or []
    if not isinstance(deps, list) or not isinstance(cases, list):
        raise ValueError("Cases JSON must contain array fields: dependencies, cases")
    return {"dependencies": deps, "cases": cases}


def _append_dependencies(ws, dependencies: list[dict]) -> None:
    ws.append(DEPENDENCY_COLUMNS)
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        req = dep.get("request") or {}
        ass = dep.get("assert") or {}
        checks = ass.get("checks") or []
        row = [
            dep.get("name", ""),
            ",".join(dep.get("depends_on") or []),
            req.get("method", "POST"),
            req.get("path", ""),
            _compact_json(req.get("headers") or {}),
            _compact_json(req.get("body") or {}),
            ass.get("status", 200),
            _compact_json(checks if isinstance(checks, list) else [str(checks)]),
            _compact_json(dep.get("extract") or {}),
        ]
        ws.append(row)


def _append_cases(ws, cases: list[dict]) -> None:
    ws.append(CASE_COLUMNS)
    for case in cases:
        if not isinstance(case, dict):
            continue
        ass = case.get("assert") or {}
        checks = ass.get("checks") or []
        steps = case.get("steps") or []
        db_assert = case.get("db_assert") or []
        row = [
            case.get("id", ""),
            case.get("name", ""),
            bool(case.get("enabled", True)),
            ass.get("status", 200),
            _compact_json(checks if isinstance(checks, list) else [str(checks)]),
            _compact_json(steps),
            _compact_json(db_assert),
        ]
        ws.append(row)


def main():
    parser = argparse.ArgumentParser(description="Cases JSON -> 2-sheet Excel")
    parser.add_argument("-i", "--input", required=True, help="Input cases.json path")
    parser.add_argument("-o", "--output", required=True, help="Output cases.xlsx path")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    plan = _load_plan(in_path)

    wb = Workbook()
    ws_dep = wb.active
    ws_dep.title = "dependencies"
    _append_dependencies(ws_dep, plan["dependencies"])

    ws_cases = wb.create_sheet("cases")
    _append_cases(ws_cases, plan["cases"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
