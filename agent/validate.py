from __future__ import annotations

import ast
import re


ALLOWED_IMPORTS = {"math", "datetime"}
DENYLIST = (
    "import os",
    "subprocess",
    "open(",
    "exec",
    "eval",
    "__",
    "requests",
    "socket",
)
CHECK_NAME = re.compile(r"^check_[a-z_]+$")


def _top_level_functions(tree: ast.Module) -> list[ast.FunctionDef]:
    return [node for node in tree.body if isinstance(node, ast.FunctionDef)]


def _import_root(name: str) -> str:
    return name.split(".", 1)[0]


def _validate_imports(tree: ast.Module) -> tuple[bool, str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _import_root(alias.name)
                if root not in ALLOWED_IMPORTS:
                    return False, f"import '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = _import_root(module)
            if root not in ALLOWED_IMPORTS:
                return False, f"import from '{module}' is not allowed"
    return True, "imports OK"


def validate_code(code: str) -> tuple[bool, str]:
    lowered = code.lower()
    for denied in DENYLIST:
        if denied in lowered:
            return False, f"denylisted token found: {denied}"

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return False, f"does not parse: {error.msg}"

    funcs = _top_level_functions(tree)
    if len(funcs) != 1:
        return False, f"expected exactly one top-level function, found {len(funcs)}"

    fn_name = funcs[0].name
    if not CHECK_NAME.fullmatch(fn_name):
        return False, f"function name must match check_[a-z_]+, got {fn_name}"

    imports_ok, why = _validate_imports(tree)
    if not imports_ok:
        return False, why

    return True, "ok"
