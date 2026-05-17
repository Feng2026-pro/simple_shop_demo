#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export MySQL information_schema for API plan db_assert generation.

Usage examples:
  python .cursor/skills/api-test-generator/scripts/export_db_schema.py \
    --output docs/demo_project_db_schema.json

  python .cursor/skills/api-test-generator/scripts/export_db_schema.py \
    --host 127.0.0.1 --port 3306 --name demo_project \
    --user root --password 123456 --output docs/demo_project_db_schema.json
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pymysql


def read_env_file(env_path: Path) -> dict:
    if not env_path.exists():
        return {}
    result = {}
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        result[key.strip()] = val.strip()
    return result


def pick(name: str, cli_val: str | None, env_map: dict, default: str | None = None) -> str | None:
    if cli_val is not None and str(cli_val).strip() != "":
        return str(cli_val).strip()
    if os.getenv(name):
        return os.getenv(name, "").strip()
    if env_map.get(name):
        return str(env_map[name]).strip()
    return default


def main() -> int:
    parser = argparse.ArgumentParser(description="Export DB schema from information_schema.")
    parser.add_argument("--env-file", default="config/.env", help="env file path, default: config/.env")
    parser.add_argument("--host")
    parser.add_argument("--port")
    parser.add_argument("--name", help="database name")
    parser.add_argument("--user")
    parser.add_argument("--password")
    parser.add_argument("--charset")
    parser.add_argument("--output", required=True, help="output json path, e.g. docs/demo_project_db_schema.json")
    args = parser.parse_args()

    env_map = read_env_file(Path(args.env_file))
    db_host = pick("DB_HOST", args.host, env_map)
    db_port = int(pick("DB_PORT", args.port, env_map, "3306"))
    db_name = pick("DB_NAME", args.name, env_map)
    db_user = pick("DB_USER", args.user, env_map)
    db_pass = pick("DB_PASS", args.password, env_map)
    db_charset = pick("DB_CHARSET", args.charset, env_map, "utf8mb4")

    missing = [k for k, v in {
        "DB_HOST": db_host,
        "DB_PORT": db_port,
        "DB_NAME": db_name,
        "DB_USER": db_user,
        "DB_PASS": db_pass,
    }.items() if v in (None, "")]
    if missing:
        raise SystemExit(f"Missing DB config: {', '.join(missing)}")

    conn = pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_pass,
        database=db_name,
        charset=db_charset,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",
                (db_name,),
            )
            tables = [r[0] for r in cur.fetchall()]

            cur.execute(
                "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_KEY "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME, ORDINAL_POSITION",
                (db_name,),
            )
            rows = cur.fetchall()

        table_cols: dict[str, list[dict]] = {}
        for t, c, dt, nullable, key in rows:
            table_cols.setdefault(t, []).append(
                {
                    "column_name": c,
                    "data_type": dt,
                    "is_nullable": nullable,
                    "column_key": key,
                }
            )

        payload = {"database": db_name, "tables": []}
        for table_name in tables:
            cols = table_cols.get(table_name, [])
            payload["tables"].append(
                {
                    "table_name": table_name,
                    "columns": cols,
                    "primary_keys": [x["column_name"] for x in cols if x["column_key"] == "PRI"],
                    "unique_keys": [x["column_name"] for x in cols if x["column_key"] == "UNI"],
                }
            )

        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exported schema: {out} (tables={len(tables)})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
