"""Full-fidelity Python parser built on the stdlib `ast` module."""

import ast
from pathlib import Path

from app.agents.ast_parser.base import ParsedClass, ParsedFile, ParsedFunction, ParsedImport


def _call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _call_name(node.func)
    return None


def _decorator_name(node: ast.expr) -> str:
    name = _call_name(node)
    if name:
        return name
    try:
        return ast.dump(node)[:40]
    except Exception:
        return "<decorator>"


def _calls_in(node: ast.AST) -> list[str]:
    calls: list[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            name = _call_name(n.func)
            if name:
                calls.append(name)
    return calls


def _build_function(node: ast.FunctionDef | ast.AsyncFunctionDef, prefix: str) -> ParsedFunction:
    qualified = f"{prefix}.{node.name}" if prefix else node.name
    return ParsedFunction(
        name=node.name,
        qualified_name=qualified,
        line=node.lineno,
        end_line=getattr(node, "end_lineno", node.lineno),
        parameters=[a.arg for a in node.args.args],
        decorators=[_decorator_name(d) for d in node.decorator_list],
        docstring=ast.get_docstring(node),
        is_async=isinstance(node, ast.AsyncFunctionDef),
        calls=_calls_in(node),
    )


def parse_python_file(path: Path, rel_path: str) -> ParsedFile:
    result = ParsedFile(path=rel_path, language="Python")

    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source, filename=rel_path)
    except (SyntaxError, ValueError, RecursionError) as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                result.imports.append(
                    ParsedImport(module=alias.name, names=[alias.asname or alias.name], line=node.lineno)
                )
        elif isinstance(node, ast.ImportFrom):
            result.imports.append(
                ParsedImport(module=node.module or "", names=[a.name for a in node.names], line=node.lineno)
            )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result.functions.append(_build_function(node, ""))
        elif isinstance(node, ast.ClassDef):
            bases = [b for b in (_call_name(base) for base in node.bases) if b]
            methods = [
                _build_function(item, node.name)
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            result.classes.append(
                ParsedClass(
                    name=node.name,
                    qualified_name=node.name,
                    line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno),
                    bases=bases,
                    decorators=[_decorator_name(d) for d in node.decorator_list],
                    docstring=ast.get_docstring(node),
                    methods=methods,
                )
            )

    return result
