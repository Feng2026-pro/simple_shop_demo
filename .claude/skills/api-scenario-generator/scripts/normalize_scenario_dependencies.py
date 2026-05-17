#!/usr/bin/env python3
"""
Normalize scenario.json dependency structure.

Goals:
- Ensure root has top-level `dependencies` for reusable login steps.
- Remove duplicated login actions from case `步骤` text.
- Keep case-level dependency hint in `前置依赖` / `注入方式`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

LOGIN_METHOD = "POST"
LOGIN_PATH = "/auth/login"
LOGIN_PATTERN = re.compile(r"^\s*\d+\)\s*调用\s+POST\s+/auth/login\b.*$", re.IGNORECASE)


def _read(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scenario root must be an object")
    cases = data.get("cases")
    if not isinstance(cases, list):
        raise ValueError("scenario root must include cases list")
    if "dependencies" in data and not isinstance(data.get("dependencies"), list):
        raise ValueError("dependencies must be a list")
    return data


def _split_steps(step_text: str) -> list[str]:
    lines = [ln.strip() for ln in (step_text or "").splitlines()]
    return [ln for ln in lines if ln]


def _join_steps(lines: list[str]) -> str:
    rebuilt = []
    for idx, line in enumerate(lines, start=1):
        normalized = re.sub(r"^\s*\d+\)\s*", "", line).strip()
        rebuilt.append(f"{idx}) {normalized}")
    return "\n".join(rebuilt)


def _normalize_dependency_name(dep_name: str) -> str:
    name = dep_name.strip() or "dep_login_admin"
    if not name.startswith("dep_"):
        return f"dep_{name}"
    return name


def _ensure_login_dependency(dependencies: list[dict], dep_name: str) -> None:
    normalized_name = _normalize_dependency_name(dep_name)
    existing_names = {str(d.get("name", "") or "") for d in dependencies if isinstance(d, dict)}
    if normalized_name in existing_names:
        return
    dependencies.append(
        {
            "name": normalized_name,
            "request": {
                "method": LOGIN_METHOD,
                "path": LOGIN_PATH,
                "headers": {},
                "path_params": {},
                "body": {
                    "username": "admin",
                    "password": "admin123",
                },
            },
            "assert": {
                "status": 200,
                "checks": ["$.code==200 && $.data.token && $.data.userId"],
            },
            "extract": {
                "token": "$.data.token",
                "userId": "$.data.userId",
            },
        }
    )


def normalize(data: dict) -> dict:
    out = dict(data)
    cases = [c for c in (out.get("cases") or []) if isinstance(c, dict)]
    dependencies = [d for d in (out.get("dependencies") or []) if isinstance(d, dict)]

    for case in cases:
        steps_text = str(case.get("步骤", "") or "")
        lines = _split_steps(steps_text)
        if not lines:
            continue

        removed_login = False
        kept_lines: list[str] = []
        for ln in lines:
            if LOGIN_PATTERN.match(ln):
                removed_login = True
                continue
            kept_lines.append(ln)

        if removed_login:
            dep_name = str(case.get("前置依赖", "") or "").strip() or "dep_login_admin"
            dep_name = _normalize_dependency_name(dep_name)
            _ensure_login_dependency(dependencies, dep_name)
            case["前置依赖"] = dep_name
            if not str(case.get("注入方式", "") or "").strip():
                case["注入方式"] = f"Authorization: Bearer DEP:{dep_name}.token"
            if kept_lines:
                case["步骤"] = _join_steps(kept_lines)
            else:
                # 极端情况下只有登录一步，保留原步骤避免空值
                case["步骤"] = steps_text

    out["cases"] = cases
    out["dependencies"] = dependencies
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize scenario dependencies")
    parser.add_argument("-i", "--input", required=True, help="Input scenario json")
    parser.add_argument("-o", "--output", help="Output path (default overwrite input)")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path
    normalized = normalize(_read(in_path))
    out_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Normalized scenario dependencies: {out_path}")


if __name__ == "__main__":
    main()
