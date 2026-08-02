from pathlib import Path

from app.agents.ast_parser.base import ParsedClass, ParsedFile, ParsedFunction, ParsedImport
from app.agents.ast_parser.js_ts_parser import parse_js_ts_file
from app.agents.ast_parser.python_parser import parse_python_file

__all__ = ["ParsedClass", "ParsedFile", "ParsedFunction", "ParsedImport", "parse_file"]


def parse_file(source_dir: Path, rel_path: str, language: str) -> ParsedFile:
    path = source_dir / rel_path
    if language == "Python":
        return parse_python_file(path, rel_path)
    if language in ("JavaScript", "TypeScript"):
        return parse_js_ts_file(path, rel_path, language)
    result = ParsedFile(path=rel_path, language=language)
    result.error = f"No deep parser registered for {language}"
    return result
