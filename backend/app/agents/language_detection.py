"""Language Detection Agent.

Maps file extensions to languages and tells the AST Parsing Agent which
parser (if any) is capable of deeply parsing a given file. Files whose
language has no deep parser yet are still counted by the Scanner Agent for
the language/file-count breakdown -- they just don't produce graph nodes.
"""

EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".c": "C",
    ".h": "C",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    ".m": "Objective-C",
    ".dart": "Dart",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".md": "Markdown",
    ".vue": "Vue",
    ".graphql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".tf": "Terraform",
}

# Languages the AST Parsing Agent can deeply parse (classes/functions/imports/calls).
DEEP_PARSE_LANGUAGES = {"Python", "JavaScript", "TypeScript"}

IGNORED_DIR_NAMES = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist",
    "build", ".next", "out", "target", "vendor", ".idea", ".vscode",
    ".pytest_cache", ".mypy_cache", "coverage", ".gradle", "bin", "obj",
    ".terraform", ".serverless", "egg-info",
}


def detect_language(filename: str) -> str | None:
    for ext, lang in EXTENSION_LANGUAGE_MAP.items():
        if filename.endswith(ext):
            return lang
    return None


def supports_deep_parse(language: str | None) -> bool:
    return language in DEEP_PARSE_LANGUAGES
