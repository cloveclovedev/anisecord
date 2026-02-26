import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyPlanConfig:
    """Configuration for the daily-plan feature.

    Currently reads from environment variables.
    TODO(#future): Replace with DB-backed per-user configuration for multi-user support.
    """

    channel_id: Optional[int] = None
    thread_format: str = "{date} 日報"
    schedule_hour: int = 7
    schedule_minute: int = 0
    llm_model: str = "gemini/gemini-2.5-flash"
    timezone: str = "Asia/Tokyo"
    sources: tuple[str, ...] = ("ticktick", "github")

    # TickTick credentials
    ticktick_client_id: str = ""
    ticktick_client_secret: str = ""
    ticktick_access_token: str = ""
    ticktick_refresh_token: str = ""

    # GitHub credentials
    github_token: str = ""
    github_repos: tuple[str, ...] = ()

    # Google Calendar credentials
    google_calendar_client_id: str = ""
    google_calendar_client_secret: str = ""
    google_calendar_access_token: str = ""
    google_calendar_refresh_token: str = ""

    def has_source(self, source_name: str) -> bool:
        """Check if a source is enabled AND has valid credentials."""
        if source_name not in self.sources:
            return False
        if source_name == "ticktick":
            return bool(self.ticktick_access_token)
        if source_name == "github":
            return bool(self.github_token and self.github_repos)
        if source_name == "google_calendar":
            return bool(self.google_calendar_access_token)
        return False


class DailyPlanConfigRepository:
    """Loads daily-plan configuration.

    Currently reads from environment variables.
    TODO(#future): Replace with DB fetch for per-user settings.
    """

    def get_config(self) -> DailyPlanConfig:
        channel_id_str = os.environ.get("DAILY_PLAN_CHANNEL_ID")
        sources_str = os.environ.get("DAILY_PLAN_SOURCES", "ticktick,github")
        github_repos_str = os.environ.get("GITHUB_REPOS", "")

        return DailyPlanConfig(
            channel_id=int(channel_id_str) if channel_id_str else None,
            thread_format=os.environ.get("DAILY_PLAN_THREAD_FORMAT", "{date} 日報"),
            schedule_hour=int(os.environ.get("DAILY_PLAN_SCHEDULE_HOUR", "7")),
            schedule_minute=int(os.environ.get("DAILY_PLAN_SCHEDULE_MINUTE", "0")),
            llm_model=os.environ.get(
                "DAILY_PLAN_LLM_MODEL", "gemini/gemini-2.5-flash"
            ),
            timezone=os.environ.get("DAILY_PLAN_TIMEZONE", "Asia/Tokyo"),
            sources=tuple(s.strip() for s in sources_str.split(",") if s.strip()),
            ticktick_client_id=os.environ.get("TICKTICK_CLIENT_ID", ""),
            ticktick_client_secret=os.environ.get("TICKTICK_CLIENT_SECRET", ""),
            ticktick_access_token=os.environ.get("TICKTICK_ACCESS_TOKEN", ""),
            ticktick_refresh_token=os.environ.get("TICKTICK_REFRESH_TOKEN", ""),
            github_token=os.environ.get("GITHUB_TOKEN", ""),
            github_repos=tuple(
                r.strip() for r in github_repos_str.split(",") if r.strip()
            ),
            google_calendar_client_id=os.environ.get("GOOGLE_CALENDAR_CLIENT_ID", ""),
            google_calendar_client_secret=os.environ.get(
                "GOOGLE_CALENDAR_CLIENT_SECRET", ""
            ),
            google_calendar_access_token=os.environ.get(
                "GOOGLE_CALENDAR_ACCESS_TOKEN", ""
            ),
            google_calendar_refresh_token=os.environ.get(
                "GOOGLE_CALENDAR_REFRESH_TOKEN", ""
            ),
        )


def load_calendar_context(config_path: Path) -> str:
    """Load calendar interpretation rules from TOML file or environment variable.

    Priority: TOML file > DAILY_PLAN_CALENDAR_CONTEXT env var.
    """
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        context = data.get("calendar", {}).get("context", "")
        if context:
            return context
    except FileNotFoundError:
        logger.debug("Config file not found: %s, checking env var", config_path)
    except tomllib.TOMLDecodeError:
        logger.warning("Failed to parse TOML: %s, checking env var", config_path)

    return os.environ.get("DAILY_PLAN_CALENDAR_CONTEXT", "")
