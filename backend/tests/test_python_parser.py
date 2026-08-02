from pathlib import Path

from app.agents.ast_parser.python_parser import parse_python_file

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_parse_models_file():
    result = parse_python_file(FIXTURE / "app" / "models.py", "app/models.py")

    assert result.error is None
    class_names = {c.name for c in result.classes}
    assert class_names == {"User", "AdminUser"}

    admin = next(c for c in result.classes if c.name == "AdminUser")
    assert admin.bases == ["User"]
    assert {m.name for m in admin.methods} >= {"__init__", "audit"}

    user = next(c for c in result.classes if c.name == "User")
    greet = next(m for m in user.methods if m.name == "greet")
    assert greet.docstring == "Return a greeting for this user."


def test_parse_services_file_captures_calls():
    result = parse_python_file(FIXTURE / "app" / "services.py", "app/services.py")
    assert result.error is None
    service = next(c for c in result.classes if c.name == "UserService")
    create_user = next(m for m in service.methods if m.name == "create_user")
    assert "User" in create_user.calls


def test_parse_syntax_error_does_not_raise(tmp_path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n    pass")
    result = parse_python_file(bad_file, "bad.py")
    assert result.error is not None
