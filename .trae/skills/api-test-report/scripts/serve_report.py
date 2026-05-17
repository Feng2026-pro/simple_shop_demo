#!/usr/bin/env python3
"""
根据已有 allure-results 生成并打开 Allure 报告。
若未安装 Allure CLI，打印安装指引并退出。
在项目根目录执行；默认结果目录为 allure-results。

Usage:
    serve_report.py           # generate + serve（打开浏览器）
    serve_report.py --no-open # 仅 generate 到 allure-report/
"""

import subprocess
import sys
from pathlib import Path

# skill/scripts -> skill -> skills -> .cursor -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
ALLURE_RESULTS = PROJECT_ROOT / "allure-results"
ALLURE_REPORT = PROJECT_ROOT / "allure-report"
INSTALL_REF = Path(__file__).resolve().parent.parent / "references" / "install.md"


def check_allure() -> bool:
    try:
        subprocess.run(
            ["allure", "--version"],
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def print_install_guide():
    print("Allure CLI 未安装或未加入 PATH。")
    print("\n安装方式（任选其一）：")
    print("  macOS:   brew install allure")
    print("  Windows: scoop install allure")
    print("  Linux:   sdk install allure")
    print("\n更多方式见:", INSTALL_REF)
    print("官方文档: https://docs.qameta.io/allure/")
    print("\n安装完成后在项目根目录执行: allure serve allure-results")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate and optionally serve Allure report from allure-results")
    parser.add_argument("--no-open", action="store_true", help="Only generate report to allure-report/, do not serve")
    args = parser.parse_args()

    if not check_allure():
        print_install_guide()
        sys.exit(1)

    if not ALLURE_RESULTS.exists() or not any(ALLURE_RESULTS.iterdir()):
        print(f"未找到 allure 数据目录或目录为空: {ALLURE_RESULTS}")
        print("请先运行接口测试（如 api-test-runner）生成 allure-results。")
        sys.exit(1)

    # generate
    r = subprocess.run(
        ["allure", "generate", str(ALLURE_RESULTS), "-o", str(ALLURE_REPORT), "--clean"],
        cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        sys.exit(r.returncode)
    print(f"Report generated: {ALLURE_REPORT}/index.html")

    if not args.no_open:
        subprocess.run(["allure", "serve", str(ALLURE_RESULTS)], cwd=PROJECT_ROOT, check=False)
    sys.exit(0)


if __name__ == "__main__":
    main()
