"""JavaScript / TypeScript parser built on tree-sitter (prebuilt grammars via
tree_sitter_languages -- no C compiler required).

Extracts top-level classes (+ methods), functions (function declarations and
named arrow-function/function-expression assignments), imports, and best-effort
call names within each function body.
"""

from pathlib import Path

from tree_sitter_languages import get_parser

from app.agents.ast_parser.base import ParsedClass, ParsedFile, ParsedFunction, ParsedImport

_GRAMMAR_BY_LANGUAGE = {
    "JavaScript": "javascript",
    "TypeScript": "typescript",
}

_PARSER_CACHE: dict[str, object] = {}


def _parser_for(grammar: str):
    if grammar not in _PARSER_CACHE:
        _PARSER_CACHE[grammar] = get_parser(grammar)
    return _PARSER_CACHE[grammar]


def _text(source: bytes, node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _find_child_by_type(node, type_name: str):
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _extract_calls(node, source: bytes) -> list[str]:
    calls: list[str] = []

    def walk(n):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn is not None:
                if fn.type == "identifier":
                    calls.append(_text(source, fn))
                elif fn.type == "member_expression":
                    prop = fn.child_by_field_name("property")
                    if prop is not None:
                        calls.append(_text(source, prop))
        for child in n.children:
            walk(child)

    walk(node)
    return calls


def _extract_params(params_node, source: bytes) -> list[str]:
    if params_node is None:
        return []
    names = []
    for child in params_node.children:
        if child.type in ("identifier", "required_parameter", "optional_parameter"):
            ident = child if child.type == "identifier" else _find_child_by_type(child, "identifier")
            if ident is not None:
                names.append(_text(source, ident))
        elif child.type == "object_pattern":
            names.append("{...}")
    return names


def _build_function(node, source: bytes, name: str, prefix: str) -> ParsedFunction:
    qualified = f"{prefix}.{name}" if prefix else name
    params_node = node.child_by_field_name("parameters")
    is_async = any(c.type == "async" for c in node.children)
    return ParsedFunction(
        name=name,
        qualified_name=qualified,
        line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_params(params_node, source),
        decorators=[],
        docstring=None,
        is_async=is_async,
        calls=_extract_calls(node, source),
    )


def parse_js_ts_file(path: Path, rel_path: str, language: str) -> ParsedFile:
    result = ParsedFile(path=rel_path, language=language)
    grammar = _GRAMMAR_BY_LANGUAGE.get(language)
    if grammar is None:
        result.error = f"Unsupported language for JS/TS parser: {language}"
        return result

    try:
        source = path.read_bytes()
        parser = _parser_for(grammar)
        tree = parser.parse(source)
    except Exception as exc:  # tree-sitter grammar/runtime errors -- never crash the pipeline
        result.error = f"{type(exc).__name__}: {exc}"
        return result

    root = tree.root_node

    def handle_class(node):
        name_node = node.child_by_field_name("name")
        name = _text(source, name_node) if name_node else "<anonymous>"
        heritage = _find_child_by_type(node, "class_heritage")
        bases: list[str] = []
        if heritage is not None:
            ident = _find_child_by_type(heritage, "identifier")
            if ident is not None:
                bases.append(_text(source, ident))

        body = node.child_by_field_name("body")
        methods: list[ParsedFunction] = []
        if body is not None:
            for member in body.children:
                if member.type == "method_definition":
                    m_name_node = member.child_by_field_name("name")
                    m_name = _text(source, m_name_node) if m_name_node else "<anonymous>"
                    methods.append(_build_function(member, source, m_name, name))

        result.classes.append(
            ParsedClass(
                name=name,
                qualified_name=name,
                line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                bases=bases,
                decorators=[],
                docstring=None,
                methods=methods,
            )
        )

    def handle_import(node):
        source_node = node.child_by_field_name("source")
        module = _text(source, source_node).strip("'\"") if source_node else ""
        result.imports.append(ParsedImport(module=module, names=[], line=node.start_point[0] + 1))

    def handle_function_declaration(node):
        name_node = node.child_by_field_name("name")
        name = _text(source, name_node) if name_node else "<anonymous>"
        result.functions.append(_build_function(node, source, name, ""))

    def handle_variable_declarator(node):
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None:
            return
        if value_node.type in ("arrow_function", "function", "function_expression"):
            name = _text(source, name_node)
            result.functions.append(_build_function(value_node, source, name, ""))

    def walk_top_level(node):
        for child in node.children:
            if child.type == "class_declaration":
                handle_class(child)
            elif child.type == "import_statement":
                handle_import(child)
            elif child.type == "function_declaration":
                handle_function_declaration(child)
            elif child.type == "lexical_declaration" or child.type == "variable_declaration":
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        handle_variable_declarator(declarator)
            elif child.type == "export_statement":
                walk_top_level(child)

    walk_top_level(root)
    return result
