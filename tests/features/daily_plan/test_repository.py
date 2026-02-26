import os
from unittest.mock import patch

from bot.features.daily_plan.repository import (
    DailyPlanConfig,
    DailyPlanConfigRepository,
)


class TestDailyPlanConfigRepository:
    def test_loads_defaults_when_no_env_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.channel_id is None
        assert config.thread_format == "{date} 日報"
        assert config.schedule_hour == 7
        assert config.schedule_minute == 0
        assert config.llm_model == "gemini/gemini-3.1-pro-preview"
        assert config.timezone == "Asia/Tokyo"
        assert config.sources == ("ticktick", "github")

    def test_loads_from_env_vars(self):
        env = {
            "DAILY_PLAN_CHANNEL_ID": "123456789",
            "DAILY_PLAN_THREAD_FORMAT": "{date} daily",
            "DAILY_PLAN_SCHEDULE_HOUR": "9",
            "DAILY_PLAN_SCHEDULE_MINUTE": "30",
            "DAILY_PLAN_LLM_MODEL": "gemini/gemini-2.5-flash",
            "DAILY_PLAN_TIMEZONE": "US/Eastern",
            "DAILY_PLAN_SOURCES": "ticktick",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.channel_id == 123456789
        assert config.thread_format == "{date} daily"
        assert config.schedule_hour == 9
        assert config.schedule_minute == 30
        assert config.llm_model == "gemini/gemini-2.5-flash"
        assert config.timezone == "US/Eastern"
        assert config.sources == ("ticktick",)

    def test_ticktick_config_from_env(self):
        env = {
            "TICKTICK_CLIENT_ID": "cid",
            "TICKTICK_CLIENT_SECRET": "csec",
            "TICKTICK_ACCESS_TOKEN": "at",
            "TICKTICK_REFRESH_TOKEN": "rt",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.ticktick_client_id == "cid"
        assert config.ticktick_client_secret == "csec"
        assert config.ticktick_access_token == "at"
        assert config.ticktick_refresh_token == "rt"

    def test_github_config_from_env(self):
        env = {
            "GITHUB_TOKEN": "ghp_xxx",
            "GITHUB_REPOS": "owner/repo1,owner/repo2",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.github_token == "ghp_xxx"
        assert config.github_repos == ("owner/repo1", "owner/repo2")

    def test_has_source_checks_sources_and_credentials(self):
        env = {
            "DAILY_PLAN_SOURCES": "ticktick,github",
            "TICKTICK_CLIENT_ID": "cid",
            "TICKTICK_CLIENT_SECRET": "csec",
            "TICKTICK_ACCESS_TOKEN": "at",
            "TICKTICK_REFRESH_TOKEN": "rt",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.has_source("ticktick") is True
        assert config.has_source("github") is False  # no GITHUB_TOKEN


class TestDailyPlanConfig:
    def test_frozen(self):
        config = DailyPlanConfig()
        try:
            config.timezone = "US/Pacific"
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestGoogleCalendarConfig:
    def test_google_calendar_config_from_env(self):
        env = {
            "GOOGLE_CALENDAR_CLIENT_ID": "gc_cid",
            "GOOGLE_CALENDAR_CLIENT_SECRET": "gc_csec",
            "GOOGLE_CALENDAR_ACCESS_TOKEN": "gc_at",
            "GOOGLE_CALENDAR_REFRESH_TOKEN": "gc_rt",
        }
        with patch.dict(os.environ, env, clear=True):
            repo = DailyPlanConfigRepository()
            config = repo.get_config()

        assert config.google_calendar_client_id == "gc_cid"
        assert config.google_calendar_client_secret == "gc_csec"
        assert config.google_calendar_access_token == "gc_at"
        assert config.google_calendar_refresh_token == "gc_rt"

    def test_has_source_google_calendar(self):
        env = {
            "DAILY_PLAN_SOURCES": "google_calendar",
            "GOOGLE_CALENDAR_CLIENT_ID": "cid",
            "GOOGLE_CALENDAR_CLIENT_SECRET": "csec",
            "GOOGLE_CALENDAR_ACCESS_TOKEN": "at",
            "GOOGLE_CALENDAR_REFRESH_TOKEN": "rt",
        }
        with patch.dict(os.environ, env, clear=True):
            config = DailyPlanConfigRepository().get_config()

        assert config.has_source("google_calendar") is True

    def test_has_source_google_calendar_missing_token(self):
        env = {
            "DAILY_PLAN_SOURCES": "google_calendar",
        }
        with patch.dict(os.environ, env, clear=True):
            config = DailyPlanConfigRepository().get_config()

        assert config.has_source("google_calendar") is False


class TestLoadCalendarContext:
    def test_loads_context_from_toml(self, tmp_path):
        toml_content = b'[calendar]\ncontext = "cloveclove is personal business."'
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(toml_content)

        from bot.features.daily_plan.repository import load_calendar_context

        result = load_calendar_context(toml_file)
        assert result == "cloveclove is personal business."

    def test_falls_back_to_env_when_file_missing(self, tmp_path):
        from bot.features.daily_plan.repository import load_calendar_context

        with patch.dict(
            os.environ, {"DAILY_PLAN_CALENDAR_CONTEXT": "env context"}, clear=False
        ):
            result = load_calendar_context(tmp_path / "nonexistent.toml")
        assert result == "env context"

    def test_falls_back_to_env_when_no_calendar_section(self, tmp_path):
        toml_content = b'[other]\nkey = "value"'
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(toml_content)

        from bot.features.daily_plan.repository import load_calendar_context

        with patch.dict(
            os.environ, {"DAILY_PLAN_CALENDAR_CONTEXT": "env fallback"}, clear=False
        ):
            result = load_calendar_context(toml_file)
        assert result == "env fallback"

    def test_returns_empty_when_no_file_and_no_env(self, tmp_path):
        from bot.features.daily_plan.repository import load_calendar_context

        with patch.dict(os.environ, {}, clear=True):
            result = load_calendar_context(tmp_path / "nonexistent.toml")
        assert result == ""

    def test_toml_takes_priority_over_env(self, tmp_path):
        toml_content = b'[calendar]\ncontext = "from toml"'
        toml_file = tmp_path / "config.toml"
        toml_file.write_bytes(toml_content)

        from bot.features.daily_plan.repository import load_calendar_context

        with patch.dict(
            os.environ, {"DAILY_PLAN_CALENDAR_CONTEXT": "from env"}, clear=False
        ):
            result = load_calendar_context(toml_file)
        assert result == "from toml"
