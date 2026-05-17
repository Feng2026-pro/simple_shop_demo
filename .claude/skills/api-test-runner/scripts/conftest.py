"""
Pytest fixtures for JSON cases-driven API tests.
Supports cases.json with top-level dependencies + cases.
run_tests.py chdirs to project root before pytest, so project_root = cwd().
"""

import json
import logging
import os
import re
from pathlib import Path
from collections import deque

import pytest

# 请求/响应日志：运行时可看到每个请求的 method、url、headers、body 与响应状态、body
logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("urllib3").setLevel(logging.WARNING)
import requests

from test_api import _send_http_request

# JSON cases cache for fixtures/generate_tests reuse
_plan_cache: dict = {}
_EMBEDDED_REF = re.compile(r"ENV:[A-Za-z0-9_]+|DEP:[A-Za-z0-9_]+\.[A-Za-z0-9_]+")


def _project_root() -> Path:
    """Project root: run_tests.py chdirs here before invoking pytest."""
    return Path.cwd()


def _project_root_from_file() -> Path:
    """从 conftest 文件位置推导项目根（scripts -> api-test-runner -> skills -> .cursor -> root）。"""
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def _load_dotenv():
    """加载 config/.env 到 os.environ，供前置依赖等使用。"""
    root = _project_root_from_file()
    env_file = root / "config" / ".env"
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


# 导入时即加载 .env，保证 session fixture 执行前已有环境变量
_load_dotenv()


def _resolve_url(url_template: str) -> str:
    base = os.environ.get("BASE_URL", "http://localhost:8080")
    return url_template.replace("${BASE_URL}", base)


def _extract_json_path(obj: dict, path: str):
    """Simple JSONPath-like extract: $.data.token -> obj['data']['token']"""
    if not path or not path.startswith("$."):
        return None
    keys = path[2:].split(".")
    cur = obj
    for k in keys:
        cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            break
    return cur


def _resolve_body(body: dict) -> dict:
    out = {}
    for k, v in (body or {}).items():
        if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
            out[k] = os.environ.get(v[2:-1], "")
        else:
            out[k] = v
    return out


def _resolve_ref_value(value, dep_outputs: dict):
    if isinstance(value, str):
        if value.startswith("ENV:"):
            return os.environ.get(value[4:], "")
        if value.startswith("DEP:"):
            ref = value[4:]
            dep_name, _, field = ref.partition(".")
            if not dep_name or not field:
                raise ValueError(f"Invalid DEP reference: {value}")
            dep_data = dep_outputs.get(dep_name) or {}
            if field not in dep_data:
                raise ValueError(f"Dependency output not found: {value}")
            return dep_data.get(field)
        if value.startswith("${") and value.endswith("}"):
            return os.environ.get(value[2:-1], "")
        # 支持字符串内嵌引用，如 "Bearer DEP:dep_login_admin.token"
        if _EMBEDDED_REF.search(value):
            def _repl(m: re.Match) -> str:
                tok = m.group(0)
                return str(_resolve_ref_value(tok, dep_outputs))
            return _EMBEDDED_REF.sub(_repl, value)
    if isinstance(value, dict):
        return {k: _resolve_ref_value(v, dep_outputs) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_ref_value(v, dep_outputs) for v in value]
    return value


def _build_dep_graph(dep_items: list[dict]) -> list[str]:
    names = [item.get("name", "").strip() for item in dep_items]
    if not all(names):
        raise ValueError("Each dependency item must include non-empty name")
    if len(names) != len(set(names)):
        raise ValueError("Dependency names must be unique")

    indegree = {name: 0 for name in names}
    edges = {name: [] for name in names}

    for item in dep_items:
        name = item["name"].strip()
        for parent in item.get("depends_on") or []:
            if parent not in indegree:
                raise ValueError(f"depends_on references unknown dependency: {parent}")
            edges[parent].append(name)
            indegree[name] += 1

    queue = deque([k for k, v in indegree.items() if v == 0])
    order = []
    while queue:
        cur = queue.popleft()
        order.append(cur)
        for nxt in edges[cur]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(names):
        raise ValueError("Circular dependency detected in JSON dependencies")
    return order


def _validate_json_case(case: dict) -> None:
    """Each case must have exactly one of: non-empty request, or non-empty steps[]."""
    if not isinstance(case, dict):
        raise ValueError("Each case in JSON plan must be an object")
    cid = case.get("id")
    if not cid:
        raise ValueError("Each JSON case must include id")
    request = case.get("request")
    steps_raw = case.get("steps")
    if steps_raw is not None and not isinstance(steps_raw, list):
        raise ValueError(f"JSON case {cid}: 'steps' must be an array if present")
    steps = steps_raw or []
    has_request = bool(request)
    has_steps = len(steps) > 0
    if has_request and has_steps:
        raise ValueError(f"JSON case {cid}: fields 'request' and 'steps' are mutually exclusive")
    if not has_request and not has_steps:
        raise ValueError(f"JSON case {cid}: must have either 'request' or non-empty 'steps'")
    if has_steps:
        names: list[str] = []
        for i, st in enumerate(steps):
            if not isinstance(st, dict):
                raise ValueError(f"JSON case {cid}: step {i} must be an object")
            name = (st.get("name") or "").strip()
            if not name:
                raise ValueError(f"JSON case {cid}: step {i} missing non-empty 'name'")
            names.append(name)
            has_api = bool((st.get("api") or "").strip())
            has_req = bool(st.get("request"))
            if has_api == has_req:
                raise ValueError(
                    f"JSON case {cid} step '{name}': exactly one of 'api' or 'request' is required"
                )
        if len(names) != len(set(names)):
            raise ValueError(f"JSON case {cid}: step 'name' values must be unique")


def _validate_step_api_refs(plan: dict, apis: dict) -> None:
    """When apiCatalog is loaded, ensure each step.api exists."""
    for case in plan.get("cases") or []:
        if not isinstance(case, dict):
            continue
        cid = case.get("id", "")
        for st in case.get("steps") or []:
            if not isinstance(st, dict):
                continue
            api_key = (st.get("api") or "").strip()
            if not api_key:
                continue
            if api_key not in apis:
                raise ValueError(f"JSON case {cid}: unknown api catalog key '{api_key}'")


def _load_json_plan(plan_path: Path) -> dict:
    if not plan_path.exists():
        raise ValueError(f"JSON cases file not found: {plan_path}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("JSON cases root must be an object")
    dependencies = plan.get("dependencies") or []
    cases = plan.get("cases") or []
    if not isinstance(dependencies, list) or not isinstance(cases, list):
        raise ValueError("JSON cases fields 'dependencies' and 'cases' must be arrays")
    for case in cases:
        _validate_json_case(case)
    return plan


# Session-level API catalog (currently optional; kept for executor compatibility)
_API_CATALOG_APIS: dict = {}


def pytest_configure(config):
    """JSON-cases mode: keep empty api catalog unless future extension sets it."""
    global _API_CATALOG_APIS
    _API_CATALOG_APIS = {}


@pytest.fixture(scope="session")
def auth_cookie(pytestconfig):
    """
    按 JSON cases 的 dependencies 执行前置依赖，返回 { 依赖名: { 提取字段: 值 } }。
    """
    json_plan = pytestconfig.getoption("json_plan", default=None)
    outputs = {}

    if json_plan:
        global _plan_cache
        plan_path = Path(json_plan)
        plan = _plan_cache if _plan_cache else _load_json_plan(plan_path)
        _plan_cache = plan
        dep_items = plan.get("dependencies") or []
        if not dep_items:
            return outputs
        order = _build_dep_graph(dep_items)
        item_by_name = {item["name"]: item for item in dep_items}
        for dep_name in order:
            dep = item_by_name[dep_name]
            req = dep.get("request") or {}
            method = (req.get("method") or "POST").upper()
            url = _resolve_url(f"${{BASE_URL}}{req.get('path', '')}" if req.get("path") else req.get("url", ""))
            headers = _resolve_ref_value(req.get("headers") or {}, outputs)
            body = _resolve_ref_value(req.get("body") or {}, outputs)
            if not url:
                raise ValueError(f"Dependency {dep_name} missing request.path/request.url")
            resp = _send_http_request(method, url, headers, body if method != "GET" else None)
            resp.raise_for_status()
            data = resp.json() if "application/json" in (resp.headers.get("content-type") or "").lower() else {}
            extract = dep.get("extract") or {}
            one = {}
            for key, path in extract.items():
                if isinstance(path, str) and path:
                    one[key] = _extract_json_path(data, path)
            outputs[dep_name] = one
        return outputs
    return outputs


def _get_first_available_token(auth_cookie: dict) -> str | None:
    """从任意前置依赖产出中取 token，兼容 user_login 等。"""
    if not auth_cookie:
        return None
    for _name, out in auth_cookie.items():
        if out and isinstance(out, dict) and out.get("token"):
            return out["token"]
    return None


def pytest_addoption(parser):
    parser.addoption("--json-cases", dest="json_plan", action="store", default=None, help="JSON test cases file path")


@pytest.fixture(scope="session")
def api_catalog():
    """JSON-cases mode currently returns empty api catalog."""
    return _API_CATALOG_APIS


@pytest.fixture
def row(request):
    """Parametrized row from JSON plan. Receives dict from parametrize."""
    return request.param if hasattr(request, "param") else {}


def pytest_generate_tests(metafunc):
    """Parametrize test_api_row with JSON cases."""
    if "row" not in metafunc.fixturenames:
        return
    json_plan = metafunc.config.getoption("json_plan", default=None)
    if not json_plan:
        metafunc.parametrize("row", [{}], indirect=True)
        return
    path = Path(json_plan)
    global _plan_cache
    _plan_cache = _load_json_plan(path)
    rows = []
    for case in _plan_cache.get("cases") or []:
        if case.get("enabled", True):
            case_row = dict(case)
            case_row["_mode"] = "json"
            rows.append(case_row)
    metafunc.parametrize("row", rows if rows else [{}], indirect=True)
