#!/usr/bin/env python3
"""
One-shot pipeline for api-scenario-generator:
scenario.json(normalize dependencies) -> scenario.xlsx
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path):
    print(">>>", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main():
    parser = argparse.ArgumentParser(description="Run scenario generation pipeline")
    parser.add_argument("-n", "--name", required=True, help="Base name, e.g. user -> docs/user_*.json/xlsx")
    parser.add_argument("--docs-dir", default="docs", help="Docs directory relative to project root")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    docs_dir = (project_root / args.docs_dir).resolve()
    name = args.name

    scenario_json = docs_dir / f"{name}_scenario.json"
    scenario_xlsx = docs_dir / f"{name}_scenario.xlsx"

    if not scenario_json.exists():
        raise SystemExit(f"Input not found: {scenario_json}")

    normalize = project_root / ".cursor" / "skills" / "api-scenario-generator" / "scripts" / "normalize_scenario_dependencies.py"
    sjson2xlsx = project_root / ".cursor" / "skills" / "api-scenario-generator" / "scripts" / "scenario_json_to_excel.py"

    _run([sys.executable, str(normalize), "-i", str(scenario_json)], project_root)
    _run([sys.executable, str(sjson2xlsx), "-i", str(scenario_json), "-o", str(scenario_xlsx)], project_root)

    # 如果 scenario.xlsx 被占用，scenario_json_to_excel.py 会输出 *_scenario_generated.xlsx
    generated_xlsx = docs_dir / f"{name}_scenario_generated.xlsx"
    source_xlsx = generated_xlsx if generated_xlsx.exists() else scenario_xlsx

    print("Done.")
    print(f"- scenario json : {scenario_json}")
    print(f"- scenario xlsx : {source_xlsx}")


if __name__ == "__main__":
    main()
