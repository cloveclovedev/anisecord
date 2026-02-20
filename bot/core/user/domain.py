from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    user_id: str
    timezone: str = "Asia/Tokyo"
    language: str = "ja"
    allowed_features: tuple[str, ...] = (
        "sns-x",
        "nutrition",
        "daily-plan",
    )  # Default enabled for now
