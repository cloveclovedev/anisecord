from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class User:
    user_id: str
    timezone: str = "Asia/Tokyo"
    allowed_features: tuple[str, ...] = ("sns-x", "nutrition") # Default enabled for now
