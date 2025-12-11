from typing import Optional
from .domain import User

class UserRepository:
    def get_user(self, user_id: str) -> User:
        """
        Fetch user settings.
        Currently returns dummy data with fixed timezone.
        In real app, this would fetch from DB.
        """
        # TODO: Implement DB fetch
        return User(user_id=user_id)
