"""
JSON cases-driven API tests. Parametrized via conftest pytest_generate_tests.
Run with: run_tests.py --cases-json=docs/xxx_cases.json
"""

import json
import logging
import os
import re

import allure
import pytest
import requests
try:
    import pymysql
except ImportError:  # pragma: no cover - optional dependency
    pymysql = None

logger = logging.getLogger(__name__)

# 字符串内嵌引用，如 "Bearer DEP:auth.token"、"/api/STEP:first.id"
_EMBEDDED_REF = re.compile(r"(?:DEP|STEP):[A-Za-z0-9_]+\.[A-Za-z0-9_]+")


def _extract_json_path(obj, path: str):
    if not path or not path.startswith("$."):
        return None
    keys = path[2:].split(".")
    cur = obj
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def _apply_inject(headers: dict, extracted: dict | None, inject_spec: str):
    """根据注入方式将前置依赖产出注入请求头。extracted 为依赖的 extract 键值，支持任意占位符 {key}。"""
    if not extracted or not inject_spec or not isinstance(extracted, dict):
        return
    if inject_spec.strip().lower() == "cookie":
        return
    parts = inject_spec.split(":", 2)
    if len(parts) >= 3 and parts[0].strip().lower() == "header":
        name = parts[1].strip()
        template = parts[2].strip()
        for key, val in extracted.items():
            if val is not None and "{" + key + "}" in template:
                template = template.replace("{" + key + "}", str(val))
        if template:
            headers[name] = template


def _apply_path_params(path: str, path_params_str: str) -> str:
    """用 CSV 的「路径参数」列替换 path 中的 {key}，值为用户填写的字面量，不做占位符替换。"""
    if not path_params_str or not path_params_str.strip():
        return path
    try:
        params = json.loads(path_params_str)
    except json.JSONDecodeError:
        logger.warning("路径参数 JSON 解析失败，跳过替换: %s", path_params_str[:100])
        return path
    if not isinstance(params, dict):
        return path
    for key, val in params.items():
        if val is None:
            continue
        path = path.replace("{" + key + "}", str(val))
    return path


def _resolve_refs(value, dep_outputs: dict, step_outputs: dict | None = None):
    """Resolve ENV:, DEP:, STEP: references in strings and nested dict/list."""
    step_outputs = step_outputs or {}
    if isinstance(value, str):
        if value.startswith("ENV:"):
            return os.environ.get(value[4:], "")
        if value.startswith("DEP:"):
            ref = value[4:]
            dep_name, _, field = ref.partition(".")
            dep_data = dep_outputs.get(dep_name) or {}
            if not dep_name or not field or field not in dep_data:
                raise AssertionError(f"Invalid dependency reference: {value}")
            return dep_data.get(field)
        if value.startswith("STEP:"):
            ref = value[5:]
            step_name, _, field = ref.partition(".")
            bucket = step_outputs.get(step_name) or {}
            if not step_name or not field or field not in bucket:
                raise AssertionError(f"Invalid STEP reference: {value}")
            return bucket.get(field)
        # 整串非纯 DEP/STEP，但内含嵌入引用（如 Authorization: Bearer DEP:auth.token）
        if _EMBEDDED_REF.search(value):

            def _repl(m: re.Match) -> str:
                tok = m.group(0)
                return str(_resolve_refs(tok, dep_outputs, step_outputs))

            return _EMBEDDED_REF.sub(_repl, value)
        return value
    if isinstance(value, dict):
        return {k: _resolve_refs(v, dep_outputs, step_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, dep_outputs, step_outputs) for v in value]
    return value


def _merge_catalog_into_step(step: dict, catalog_apis: dict) -> dict:
    """Build full request dict: inline step.request, or apis[api] shallow-merged with step fields."""
    if step.get("request"):
        return dict(step["request"])
    api_key = (step.get("api") or "").strip()
    if not api_key:
        raise AssertionError("JSON step must have either 'request' or 'api'")
    base = catalog_apis.get(api_key)
    if not base or not isinstance(base, dict):
        raise AssertionError(
            f"Unknown api catalog key {api_key!r}; set plan 'apiCatalog' or pass --api-catalog"
        )
    overlay_keys = ("method", "path", "path_params", "headers", "body")
    overlay = {k: step[k] for k in overlay_keys if k in step}
    out: dict = {}
    out["method"] = overlay.get("method") or base.get("method") or "GET"
    if "path" in overlay:
        out["path"] = overlay.get("path") or ""
    else:
        out["path"] = (base.get("path") or "").strip()
    h = dict(base.get("headers") or {})
    h.update(dict(overlay.get("headers") or {}))
    out["headers"] = h
    b = dict(base.get("body") or {})
    b.update(dict(overlay.get("body") or {}))
    out["body"] = b
    pp = dict(base.get("path_params") or {})
    pp.update(dict(overlay.get("path_params") or {}))
    out["path_params"] = pp
    return out


def _prepare_json_http_parts(base_url: str, req: dict, dep_outputs: dict, step_outputs: dict):
    method = (req.get("method") or "GET").strip().upper()
    path = (req.get("path") or "").strip()
    path_params = _resolve_refs(req.get("path_params") or {}, dep_outputs, step_outputs)
    for k, v in path_params.items():
        path = path.replace("{" + str(k) + "}", str(v))
    headers = {"Content-Type": "application/json"}
    headers.update(_resolve_refs(req.get("headers") or {}, dep_outputs, step_outputs))
    body = _resolve_refs(req.get("body") or {}, dep_outputs, step_outputs) if method != "GET" else None
    url = f"{base_url.rstrip('/')}{path}"
    return method, url, headers, body


def _is_form_urlencoded(headers: dict) -> bool:
    ct = str(headers.get("Content-Type") or headers.get("content-type") or "").lower()
    return "application/x-www-form-urlencoded" in ct


def _send_http_request(method: str, url: str, headers: dict, body):
    """POST/PUT/PATCH: json body by default; form fields when Content-Type is urlencoded."""
    method = (method or "GET").strip().upper()
    kwargs = {"timeout": 30, "allow_redirects": False}
    if method == "GET":
        return requests.request(method, url, headers=headers, **kwargs)
    if _is_form_urlencoded(headers):
        return requests.request(method, url, data=body, headers=headers, **kwargs)
    return requests.request(method, url, json=body, headers=headers, **kwargs)


def _log_request_response(method, url, headers, body, resp):
    logger.info(
        "请求: %s %s | headers=%s | body=%s",
        method, url, headers, body if body is not None else "(无)",
    )
    try:
        body_log = resp.json()
        body_str = json.dumps(body_log, ensure_ascii=False)
    except Exception:
        body_str = resp.text
    if len(body_str) > 500:
        body_str = body_str[:500] + "..."
    logger.info("响应: status=%s | body=%s", resp.status_code, body_str)


def _assert_response(resp, expected_status: int, expected_check: str):
    try:
        err_body = json.dumps(resp.json(), ensure_ascii=False)[:200]
    except Exception:
        err_body = resp.text[:200]
    assert resp.status_code == expected_status, (
        f"Expected {expected_status}, got {resp.status_code}: {err_body}"
    )
    if expected_check and "application/json" in resp.headers.get("content-type", ""):
        data = resp.json()
        for part in expected_check.replace(";", "&&").split("&&"):
            part = part.strip()
            if not part:
                continue
            _evaluate_condition(data, part)


def _extract_to_map(data: dict, extract_spec: dict) -> dict:
    one = {}
    for key, path in (extract_spec or {}).items():
        if isinstance(path, str) and path:
            one[key] = _extract_json_path(data, path)
    return one


def _is_truthy_env(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "n", "off"}


def _db_runtime_state() -> tuple[bool, str]:
    if not _is_truthy_env(os.environ.get("DB_ASSERT_ENABLED"), default=True):
        return False, "DB_ASSERT_ENABLED=false"
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASS")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return False, f"missing DB config: {', '.join(missing)}"
    if pymysql is None:
        return False, "PyMySQL not installed"
    return True, "enabled"


def _sql_quote(value) -> str:
    """将 Python 值转为 db_assert SQL 片段（字符串加单引号并转义，避免 UUID 等未加引号被 MySQL 误解析）。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    s = str(value)
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def _resolve_sql_template(sql: str, dep_outputs: dict, step_outputs: dict | None = None) -> str:
    step_outputs = step_outputs or {}
    pattern = re.compile(r"ENV:[A-Za-z0-9_]+|(?:DEP|STEP):[A-Za-z0-9_]+\.[A-Za-z0-9_]+")

    def _repl(m: re.Match) -> str:
        tok = m.group(0)
        if tok.startswith("ENV:"):
            raw = os.environ.get(tok[4:], "")
        else:
            raw = _resolve_refs(tok, dep_outputs, step_outputs)
        return _sql_quote(raw)

    return pattern.sub(_repl, sql)


def _query_mysql(sql: str) -> list[dict]:
    assert pymysql is not None
    port = int(os.environ.get("DB_PORT", "3306"))
    charset = os.environ.get("DB_CHARSET", "utf8mb4")
    conn = pymysql.connect(
        host=os.environ.get("DB_HOST"),
        port=port,
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        database=os.environ.get("DB_NAME"),
        charset=charset,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        read_timeout=15,
        write_timeout=15,
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            if isinstance(rows, tuple):
                rows = list(rows)
            return rows or []
    finally:
        conn.close()


def _extract_db_left(context: dict, left: str):
    if left == "rows_count":
        return context.get("rows_count")
    if left.startswith("row0."):
        row0 = context.get("row0") or {}
        if not isinstance(row0, dict):
            return None
        return row0.get(left[5:])
    return None


def _evaluate_db_condition(context: dict, expr_str: str):
    expr = expr_str.strip()
    if not expr:
        return
    operators = [">=", "<=", ">", "<", "!=", "=="]
    op = None
    left = right = None
    for candidate in operators:
        if candidate in expr:
            parts = expr.split(candidate, 1)
            if len(parts) == 2:
                left, right = parts[0].strip(), parts[1].strip()
                op = candidate
                break
    if op is None or left is None or right is None:
        raise AssertionError(f"Unsupported db check expression: {expr_str}")
    actual = _extract_db_left(context, left)
    assert actual is not None, f"DB check failed: {left} is missing"
    expected = _parse_expected_value(right)

    if op in {">", ">=", "<", "<="}:
        actual_num = _to_number(actual)
        expected_num = _to_number(expected)
        if not isinstance(actual_num, (int, float)) or not isinstance(expected_num, (int, float)):
            raise AssertionError(
                f"DB numeric comparison requires numbers: {left}={actual!r}, expected={expected!r}"
            )
        if op == ">":
            assert actual_num > expected_num, f"DB check failed: {left} = {actual_num} !> {expected_num}"
        elif op == ">=":
            assert actual_num >= expected_num, f"DB check failed: {left} = {actual_num} !>= {expected_num}"
        elif op == "<":
            assert actual_num < expected_num, f"DB check failed: {left} = {actual_num} !< {expected_num}"
        else:
            assert actual_num <= expected_num, f"DB check failed: {left} = {actual_num} !<= {expected_num}"
        return

    actual_num = _to_number(actual)
    expected_num = _to_number(expected)
    if isinstance(actual_num, (int, float)) and isinstance(expected_num, (int, float)):
        a_val, e_val = actual_num, expected_num
    else:
        a_val, e_val = str(actual), str(expected)
    if op == "==":
        assert a_val == e_val, f"DB check failed: {left} = {a_val!r} != {e_val!r}"
    else:
        assert a_val != e_val, f"DB check failed: {left} = {a_val!r} == {e_val!r}"


def _run_db_assertions(case_row: dict, dep_outputs: dict, step_outputs: dict):
    db_asserts = case_row.get("db_assert") or []
    if not db_asserts:
        return
    enabled, reason = _db_runtime_state()
    if not enabled:
        logger.info("DB assert skipped: %s", reason)
        return
    for idx, item in enumerate(db_asserts, start=1):
        if not isinstance(item, dict):
            raise AssertionError(f"db_assert[{idx}] must be an object")
        name = (item.get("name") or f"db_assert_{idx}").strip()
        sql_tmpl = (item.get("sql") or "").strip()
        if not sql_tmpl:
            raise AssertionError(f"db_assert[{idx}] missing sql")
        sql = _resolve_sql_template(sql_tmpl, dep_outputs, step_outputs)
        with allure.step(f"DB {name}"):
            rows = _query_mysql(sql)
            logger.info("DB query: %s | rows=%s", sql, len(rows))
            checks = item.get("checks") or []
            if isinstance(checks, str):
                checks = [checks]
            context = {"rows_count": len(rows), "row0": rows[0] if rows else None}
            for expr in checks:
                if not isinstance(expr, str):
                    raise AssertionError(f"db_assert[{idx}] check must be string")
                _evaluate_db_condition(context, expr)


def _to_number(val):
    """尽量将值转换为数字，无法转换则返回原值。"""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        v = val.strip()
        try:
            if "." in v:
                return float(v)
            return int(v)
        except ValueError:
            return val
    return val


def _parse_expected_value(raw: str):
    """解析右侧期望值字符串，支持数字与字符串两类。"""
    s = raw.strip()
    # 带双引号的，去掉最外层引号，按字符串处理
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    # 纯数字或小数，按数字处理
    num = _to_number(s)
    return num


def _evaluate_condition(data: dict, expr_str: str):
    """
    解析并断言单个条件表达式。
    支持：
    - $.code==200
    - $.data.id!=1
    - $.data.total>=0
    - $.data.username==user001
    - 仅 JSONPath：$.data.token  → 断言该值为真
    """
    expr = expr_str.strip()
    if not expr:
        return

    # 运算符按长度优先匹配，避免 >= 被拆成 >
    operators = [">=", "<=", ">", "<", "!=", "=="]
    op = None
    left = right = None
    for candidate in operators:
        if candidate in expr:
            parts = expr.split(candidate, 1)
            if len(parts) == 2:
                left, right = parts[0].strip(), parts[1].strip()
                op = candidate
                break

    # 无运算符：仅做 JSONPath 存在性/真值校验
    if op is None:
        actual = _extract_json_path(data, expr)
        assert actual, f"Check failed: {expr} is falsy or missing"
        return

    actual = _extract_json_path(data, left)
    assert actual is not None, f"Check failed: {left} is missing"
    expected = _parse_expected_value(right)

    # 数值比较运算
    if op in {">", ">=", "<", "<="}:
        actual_num = _to_number(actual)
        expected_num = _to_number(expected)
        if not isinstance(actual_num, (int, float)) or not isinstance(expected_num, (int, float)):
            raise AssertionError(
                f"Numeric comparison requires number types: {left}={actual!r}, expected={expected!r}"
            )
        if op == ">":
            assert actual_num > expected_num, f"Check failed: {left} = {actual_num} !> {expected_num}"
        elif op == ">=":
            assert actual_num >= expected_num, f"Check failed: {left} = {actual_num} !>= {expected_num}"
        elif op == "<":
            assert actual_num < expected_num, f"Check failed: {left} = {actual_num} !< {expected_num}"
        else:  # <=
            assert actual_num <= expected_num, f"Check failed: {left} = {actual_num} !<= {expected_num}"
        return

    # 等值／不等值比较
    actual_num = _to_number(actual)
    expected_num = _to_number(expected)
    # 若两边都可转为数字，则按数字比较；否则按字符串比较
    if isinstance(actual_num, (int, float)) and isinstance(expected_num, (int, float)):
        a_val, e_val = actual_num, expected_num
    else:
        a_val, e_val = str(actual), str(expected)

    if op == "==":
        assert a_val == e_val, f"Check failed: {left} = {a_val!r} != {e_val!r}"
    elif op == "!=":
        assert a_val != e_val, f"Check failed: {left} = {a_val!r} == {e_val!r}"
    else:
        raise AssertionError(f"Unsupported operator in expression: {expr_str}")


def test_api_row(row, auth_cookie, api_catalog):
    """Execute one API test case from JSON plan row."""
    if not row:
        pytest.skip("No json cases data or --cases-json not specified")
    if row.get("_mode") != "json":
        pytest.skip("Unsupported row mode")

    base_url = os.environ.get("BASE_URL", "http://localhost:8080")
    dep_outputs = auth_cookie if isinstance(auth_cookie, dict) else {}
    case_id = row.get("id", "")
    case_name = row.get("name", "")
    steps = row.get("steps") or []
    step_outputs: dict[str, dict] = {}
    catalog = api_catalog if isinstance(api_catalog, dict) else {}
    with allure.step(f"{case_id} {case_name}"):
        last_resp = None
        for step in steps:
            sname = (step.get("name") or "").strip()
            with allure.step(sname):
                merged = _merge_catalog_into_step(step, catalog)
                if not (merged.get("path") or "").strip():
                    raise AssertionError(f"Step {sname!r} resolved to empty path")
                method, url, headers, body = _prepare_json_http_parts(
                    base_url, merged, dep_outputs, step_outputs
                )
                last_resp = _send_http_request(method, url, headers, body)
                _log_request_response(method, url, headers, body, last_resp)
                sa = step.get("assert") or {}
                step_status = int(sa.get("status", 200))
                sch = sa.get("checks") or []
                step_checks = " && ".join(sch) if isinstance(sch, list) else str(sch or "")
                _assert_response(last_resp, step_status, step_checks)
                data = {}
                if "application/json" in (last_resp.headers.get("content-type") or "").lower():
                    try:
                        data = last_resp.json()
                    except Exception:
                        data = {}
                step_outputs[sname] = _extract_to_map(data, step.get("extract") or {})
        expected = row.get("assert") or {}
        case_status = int(expected.get("status", 200))
        cks = expected.get("checks") or []
        case_checks = " && ".join(cks) if isinstance(cks, list) else str(cks or "")
        if last_resp is not None:
            _assert_response(last_resp, case_status, case_checks)
        _run_db_assertions(row, dep_outputs, step_outputs)
