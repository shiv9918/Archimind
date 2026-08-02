"""Domain models."""


class User:
    """Represents an application user."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def greet(self) -> str:
        """Return a greeting for this user."""
        return f"Hello, {self.name}"


class AdminUser(User):
    """A user with elevated privileges."""

    def __init__(self, name: str, email: str):
        super().__init__(name, email)
        self.is_admin = True

    def audit(self) -> str:
        return f"Auditing {self.name}"
