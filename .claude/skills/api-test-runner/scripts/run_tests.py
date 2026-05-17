#!/usr/bin/env python3
"""
Run API tests via pytest and generate Allure report.

Usage:
    run_tests.py --cases-json <cases.json> [--base-url <url>] [--serve]
    run_tests.py -c docs/api_interface_cases.json

Options:
    --cases-json, -c Path to JSON test cases file
    --base-url  Override BASE_URL for API requests
    --serve     Open Allure report in browser after run
"""

import os
import subprocess
import sys
from pathlib import Path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Run JSON test cases with pytest and Allure")
    parser.add_argument(
        "--cases-json",
        "-c",
        dest="cases_json",
        required=True,
        help="JSON test cases file path",
    )
    parser.add_argument("--base-url", default=None, help="Override BASE_URL")
    parser.add_argument("--serve", action="store_true", help="Serve Allure report after run")
    args = parser.parse_args()

    # scripts/ -> api-test-runner/ -> skills/ -> .cursor/ -> api-automation/
    project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    os.chdir(project_root)

    case_path = Path(args.cases_json)
    if not case_path.is_absolute():
        case_path = project_root / case_path
    if not case_path.exists():
        print(f"Error: JSON test cases file not found: {case_path}")
        sys.exit(1)

    if args.base_url:
        os.environ["BASE_URL"] = args.base_url

    # 加载 config/.env，供 conftest 前置登录等使用（.env 中的值覆盖已有，确保子进程可用）
    env_file = project_root / "config" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k:
                    os.environ[k] = v

    # Run pytest with skill's test + conftest (self-contained under skill)
    skill_scripts = Path(__file__).resolve().parent
    test_api_path = skill_scripts / "test_api.py"
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_api_path),
        "-v",
        "-s",
        "--alluredir=allure-results",
    ]
    cmd.append(f"--json-cases={case_path.resolve()}")
    result = subprocess.run(cmd, cwd=project_root, env=os.environ)
    if result.returncode != 0:
        print("Pytest completed with failures.")

    # Allure report (requires Allure CLI: https://docs.qameta.io/allure/#_install)
    if Path(project_root, "allure-results").exists():
        try:
            if args.serve:
                subprocess.run(["allure", "serve", "allure-results"], cwd=project_root, check=False)
            else:
                subprocess.run(["allure", "generate", "allure-results", "-o", "allure-report", "--clean"], cwd=project_root, check=False)
                print("Allure report: allure-report/index.html")
        except FileNotFoundError:
            print("Allure CLI not found. Results saved to allure-results/. Install: https://docs.qameta.io/allure/")

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
