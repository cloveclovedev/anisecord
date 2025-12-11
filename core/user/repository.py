from typing import Optional
from .domain import User

class UserRepository:
    def get_user(self, user_id: str) -> User:
        """
        Fetch user settings.
        Currently returns dummy data with fixed timezone.
        """
        # In the future, this would fetch from a database.
        return User(user_id=user_id, timezone="Asia/Tokyo")
