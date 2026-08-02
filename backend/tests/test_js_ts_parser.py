from pathlib import Path

from app.agents.ast_parser.js_ts_parser import parse_js_ts_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_parse_utils_js():
    result = parse_js_ts_file(FIXTURE / "frontend" / "src" / "utils.js", "frontend/src/utils.js", "JavaScript")

    assert result.error is None
    func_names = {f.name for f in result.functions}
    assert "add" in func_names
    assert "fetchUser" in func_names

    class_names = {c.name for c in result.classes}
    assert "ApiClient" in class_names

    api_client = next(c for c in result.classes if c.name == "ApiClient")
    method_names = {m.name for m in api_client.methods}
    assert {"constructor", "get"} <= method_names


def test_parse_invalid_language_returns_error(tmp_path):
    f = tmp_path / "x.js"
    f.write_text("function ok() {}")
    result = parse_js_ts_file(f, "x.js", "Go")
    assert result.error is not None
