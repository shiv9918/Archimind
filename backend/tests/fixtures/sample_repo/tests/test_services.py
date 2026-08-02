from app.services import UserService


def test_create_user():
    service = UserService()
    user = service.create_user("Ada", "ada@example.com")
    assert user.name == "Ada"
