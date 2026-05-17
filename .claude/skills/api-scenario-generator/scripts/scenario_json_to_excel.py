#!/usr/bin/env python3
"""
Write scenario-review Excel from *_scenario.json.

Input root:
{
  "dependencies": [ ... ],  # optional
  "cases": [ { ... column keys ... } ]
}
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook

# 与 scenario-excel-spec 保持一致（单接口 + 串联统一表）
SCENARIO_COLUMNS = [
    "场景类型",
    "场景ID",
    "场景名称",
    "测试点",
    "优先级",
    "前置条件",
    "前置依赖",
    "依赖产出提取",
    "注入方式",
    "步骤",
    "预期结果",
    "备注",
]

DEPENDENCY_COLUMNS = [
    "name",
    "depends_on",
    "请求方法",
    "接口路径",
    "请求体",
    "断言",
    "提取字段",
]


def _load_input(path: Path) -> tuple[list[dict], list[dict]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Root must be an object")
    rows = raw.get("cases")
    if not isinstance(rows, list):
        raise ValueError("Missing or invalid 'cases' array")
    deps = raw.get("dependencies") or []
    if not isinstance(deps, list):
        raise ValueError("'dependencies' must be a list when provided")
    return [x for x in rows if isinstance(x, dict)], [x for x in deps if isinstance(x, dict)]


def _derive_steps_legacy(item: dict) -> str:
    method = str(item.get("请求方法", "") or "").strip().upper()
    path = str(item.get("接口路径", "") or "").strip()
    request_text = str(item.get("关键输入（自然语言）", "") or "").strip()
    expected_text = str(item.get("预期结果（自然语言）", "") or "").strip()

    pieces = []
    if method and path:
        pieces.append(f"1) 调用 {method} {path}")
    if request_text:
        pieces.append(f"2) 请求输入：{request_text}")
    if expected_text:
        pieces.append(f"3) 响应校验：{expected_text}")
    return "\n".join(pieces)


def _normalize_item(item: dict) -> dict:
    """兼容旧字段，尽量生成可读的最少字段场景。"""
    normalized = dict(item)
    case_type = str(normalized.get("场景类型", "") or "").strip()
    normalized["场景类型"] = case_type if case_type in {"单接口", "串联"} else "串联"

    # 测试点：优先新字段，回退到旧“业务目标”
    if not str(normalized.get("测试点", "") or "").strip():
        normalized["测试点"] = str(normalized.get("业务目标", "") or "")

    # 优先级：优先新字段，回退旧风险等级，再回退 P1
    priority = str(normalized.get("优先级", "") or "").strip()
    if not priority:
        priority = str(normalized.get("风险等级（P0/P1/P2）", "") or "").strip() or "P1"
    normalized["优先级"] = priority

    # 预期结果：优先新字段，回退旧字段
    if not str(normalized.get("预期结果", "") or "").strip():
        normalized["预期结果"] = str(normalized.get("预期结果（自然语言）", "") or "")

    # 步骤：优先新字段，回退从旧接口字段自动拼接
    if not str(normalized.get("步骤", "") or "").strip():
        normalized["步骤"] = _derive_steps_legacy(normalized)

    # 依赖字段：可选，默认空字符串，保证导出列稳定
    for dep_col in ("前置依赖", "依赖产出提取", "注入方式"):
        if dep_col not in normalized or normalized.get(dep_col) is None:
            normalized[dep_col] = ""

    return normalized


def _row_values(item: dict) -> list[str]:
    out = []
    for col in SCENARIO_COLUMNS:
        v = item.get(col, "")
        if v is None:
            v = ""
        elif not isinstance(v, str):
            v = str(v)
        out.append(v)
    return out


def _infer_module(item: dict) -> str:
    text = " ".join(
        [
            str(item.get("测试点", "") or ""),
            str(item.get("步骤", "") or ""),
            str(item.get("场景名称", "") or ""),
        ]
    )
    m = re.search(r"/api/v\d+/([a-zA-Z0-9_-]+)", text)
    if m:
        return m.group(1).lower()
    if "/auth/" in text:
        return "auth"
    return "unknown"


def _infer_crud_ops(item: dict) -> set[str]:
    text = " ".join(
        [
            str(item.get("测试点", "") or ""),
            str(item.get("步骤", "") or ""),
            str(item.get("场景名称", "") or ""),
        ]
    ).lower()
    ops = set()
    if any(k in text for k in ["列表", "查询", "获取", "详情", "get "]):
        ops.add("R")
    if any(k in text for k in ["创建", "新增", "下单", "入库", "post "]):
        ops.add("C")
    if any(k in text for k in ["更新", "调整", "/status", "put "]):
        ops.add("U")
    if any(k in text for k in ["删除", "delete "]):
        ops.add("D")
    return ops


def _print_coverage_report(cases: list[dict]) -> None:
    type_counter = Counter(str(x.get("场景类型", "串联") or "串联") for x in cases)
    print(
        "Coverage summary: "
        f"单接口={type_counter.get('单接口', 0)}, 串联={type_counter.get('串联', 0)}, 总计={len(cases)}"
    )

    module_ops: dict[str, set[str]] = defaultdict(set)
    module_case_count: Counter = Counter()
    for item in cases:
        module = _infer_module(item)
        module_case_count[module] += 1
        module_ops[module].update(_infer_crud_ops(item))

    for module in sorted(module_case_count.keys()):
        missing = sorted({"C", "R", "U", "D"} - module_ops[module])
        if module == "unknown":
            print(f"WARN: {module_case_count[module]} 条用例未识别模块，建议在步骤中写明接口路径")
            continue
        if missing:
            print(
                f"WARN: 模块 {module} 可能缺少 CRUD 覆盖：缺 {','.join(missing)} "
                f"(当前 {module_case_count[module]} 条)"
            )


def _dep_row_values(dep: dict) -> list[str]:
    req = dep.get("request") or {}
    assertion = dep.get("assert") or {}
    row = [
        str(dep.get("name", "") or ""),
        str(dep.get("depends_on", "") or ""),
        str(req.get("method", "") or ""),
        str(req.get("path", "") or ""),
        json.dumps(req.get("body") or {}, ensure_ascii=False),
        json.dumps(assertion, ensure_ascii=False),
        json.dumps(dep.get("extract") or {}, ensure_ascii=False),
    ]
    return row


def main():
    parser = argparse.ArgumentParser(description="Scenario JSON -> scenario review Excel")
    parser.add_argument("-i", "--input", required=True, help="Input *_scenario.json")
    parser.add_argument("-o", "--output", required=True, help="Output .xlsx path")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    cases, dependencies = _load_input(in_path)
    if not cases:
        raise SystemExit("No cases in input file")

    normalized_cases = [_normalize_item(x) for x in cases]
    _print_coverage_report(normalized_cases)

    wb = Workbook()
    ws = wb.active
    ws.title = "cases"
    ws.append(SCENARIO_COLUMNS)
    for item in normalized_cases:
        ws.append(_row_values(item))

    if dependencies:
        ws_dep = wb.create_sheet("dependencies")
        ws_dep.append(DEPENDENCY_COLUMNS)
        for dep in dependencies:
            ws_dep.append(_dep_row_values(dep))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        wb.save(out_path)
        print(f"Wrote {out_path} (cases={len(cases)}, dependencies={len(dependencies)})")
    except OSError as e:
        alt = out_path.with_name(f"{out_path.stem}_generated{out_path.suffix}")
        wb.save(alt)
        print(
            f"WARN: could not write {out_path} ({e!r}); "
            f"wrote {alt} (cases={len(cases)}, dependencies={len(dependencies)})"
        )


if __name__ == "__main__":
    main()
