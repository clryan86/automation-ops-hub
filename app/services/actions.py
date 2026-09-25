from __future__ import annotations

import ast
import operator
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from ..config import Settings


class ActionError(RuntimeError):
    pass


def get_path(data: dict[str, Any], path: str, default: Any = None) -> Any:
    current: Any = data
    for piece in path.split("."):
        if not isinstance(current, dict) or piece not in current:
            return default
        current = current[piece]
    return current


def set_path(data: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = data
    for piece in parts[:-1]:
        if piece not in current or not isinstance(current[piece], dict):
            current[piece] = {}
        current = current[piece]
    current[parts[-1]] = value


def render_template(template: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        value = get_path(context, match.group(1).strip(), "")
        return str(value)
    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", replace, template)


def safe_calculate(expression: str, context: dict[str, Any]) -> float:
    operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
    }

    def evaluate(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            value = context.get(node.id)
            if not isinstance(value, (int, float)):
                raise ActionError(f"'{node.id}' is not numeric")
            return float(value)
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            return operators[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](evaluate(node.operand))
        raise ActionError("Unsupported calculation expression")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ActionError("Invalid calculation expression") from exc
    return evaluate(tree)


def execute_action(action: str, params: dict[str, Any], context: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if action == "set":
        path = str(params["path"])
        value = params.get("value")
        if isinstance(value, str):
            value = render_template(value, context)
        set_path(context, path, value)
        return {"path": path, "value": value}

    if action == "template":
        path = str(params["path"])
        value = render_template(str(params.get("template", "")), context)
        set_path(context, path, value)
        return {"path": path, "value": value}

    if action == "calculate":
        path = str(params["path"])
        variables = {name: get_path(context, source) for name, source in params.get("variables", {}).items()}
        value = safe_calculate(str(params["expression"]), variables)
        set_path(context, path, value)
        return {"path": path, "value": value}

    if action == "regex_extract":
        source = str(get_path(context, str(params["source"]), ""))
        pattern = re.compile(str(params["pattern"]))
        match = pattern.search(source)
        if not match:
            raise ActionError("Pattern did not match")
        value = match.group(int(params.get("group", 1)))
        path = str(params["path"])
        set_path(context, path, value)
        return {"path": path, "value": value}

    if action == "assert":
        actual = get_path(context, str(params["path"]))
        operator_name = str(params.get("operator", "equals"))
        expected = params.get("value")
        checks = {
            "equals": actual == expected,
            "not_equals": actual != expected,
            "exists": actual is not None,
            "truthy": bool(actual),
        }
        if operator_name not in checks:
            raise ActionError(f"Unsupported assert operator: {operator_name}")
        if not checks[operator_name]:
            raise ActionError(str(params.get("message", f"Assertion failed for {params['path']}")))
        return {"actual": actual, "operator": operator_name}

    if action == "http_request":
        if not settings.allow_http_actions:
            raise ActionError("HTTP actions are disabled")
        url = render_template(str(params["url"]), context)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ActionError("Invalid HTTP URL")
        if settings.http_host_allowlist and parsed.hostname.lower() not in settings.http_host_allowlist:
            raise ActionError("HTTP host is not allowlisted")
        method = str(params.get("method", "GET")).upper()
        timeout = min(float(params.get("timeout_seconds", 10)), 30.0)
        response = httpx.request(method, url, json=params.get("json"), timeout=timeout)
        response.raise_for_status()
        payload: Any
        try:
            payload = response.json()
        except ValueError:
            payload = {"text": response.text[:4000]}
        path = params.get("path")
        if path:
            set_path(context, str(path), payload)
        return {"status_code": response.status_code, "body": payload}

    raise ActionError(f"Unsupported action: {action}")
