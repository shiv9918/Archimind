"""Shared data model produced by every language-specific AST parser."""

from dataclasses import dataclass, field


@dataclass
class ParsedImport:
    module: str
    names: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class ParsedFunction:
    name: str
    qualified_name: str
    line: int
    end_line: int
    parameters: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    is_async: bool = False
    calls: list[str] = field(default_factory=list)


@dataclass
class ParsedClass:
    name: str
    qualified_name: str
    line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    methods: list[ParsedFunction] = field(default_factory=list)


@dataclass
class ParsedFile:
    path: str
    language: str
    imports: list[ParsedImport] = field(default_factory=list)
    classes: list[ParsedClass] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)
    error: str | None = None
