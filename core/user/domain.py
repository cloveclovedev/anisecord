from dataclasses import dataclass

@dataclass(frozen=True)
class User:
    user_id: str
    timezone: str = "Asia/Tokyo"
