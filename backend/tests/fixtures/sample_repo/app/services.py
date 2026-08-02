"""User service layer."""

from app.models import AdminUser, User


class UserService:
    """Handles user creation and lookups."""

    def __init__(self):
        self.users = []

    def create_user(self, name: str, email: str) -> User:
        """Create and store a new user."""
        user = User(name, email)
        self.users.append(user)
        return user

    def promote_to_admin(self, user: User) -> AdminUser:
        admin = AdminUser(user.name, user.email)
        self.users.append(admin)
        return admin


def get_default_service() -> UserService:
    return UserService()
