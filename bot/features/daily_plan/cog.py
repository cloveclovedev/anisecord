import asyncio
import datetime
import logging
from pathlib import Path
from zoneinfo import ZoneInfo

from discord import Interaction, app_commands
from discord.ext import commands, tasks

from bot.core.user.decorators import feature_enabled
from bot.services.discord.repository import DiscordRepository
from bot.services.github.repository import GitHubRepository
from bot.services.google_calendar.auth import GoogleCalendarAuth
from bot.services.google_calendar.repository import GoogleCalendarRepository
from bot.services.llm.repository import LLMRepository
from bot.services.ticktick.auth import TickTickAuth
from bot.services.ticktick.repository import TickTickRepository

from .domain import (
    ContextSource,
    DailyPlanPromptBuilder,
    GitHubTaskSource,
    GoogleCalendarContextSource,
    TaskSource,
    TickTickTaskSource,
)
from .repository import DailyPlanConfigRepository, load_calendar_context

logger = logging.getLogger(__name__)


class DailyPlanCog(commands.Cog):
    """Generate and post daily plans from external task sources."""

    def __init__(self, bot):
        self.bot = bot
        self.config_repo = DailyPlanConfigRepository()
        self.discord_repo = DiscordRepository()

        # Load config once at init
        self._config = self.config_repo.get_config()

        # LLM with configurable model
        self.llm_repo = LLMRepository(
            model_name=self._config.llm_model,
            api_key=self.bot.gemini_api_key,
        )

        # Build task sources based on config
        self._sources: list[TaskSource] = []
        self._init_sources()
        self._context_sources: list[ContextSource] = []
        self._init_context_sources()

    def _init_sources(self) -> None:
        """Initialize enabled task sources."""
        if self._config.has_source("ticktick"):
            auth = TickTickAuth(
                client_id=self._config.ticktick_client_id,
                client_secret=self._config.ticktick_client_secret,
                access_token=self._config.ticktick_access_token,
                refresh_token=self._config.ticktick_refresh_token,
            )
            self._sources.append(TickTickTaskSource(TickTickRepository(auth)))

        if self._config.has_source("github"):
            self._sources.append(
                GitHubTaskSource(
                    GitHubRepository(
                        token=self._config.github_token,
                        repos=list(self._config.github_repos),
                    )
                )
            )

    def _init_context_sources(self) -> None:
        """Initialize enabled context sources."""
        if self._config.has_source("google_calendar"):
            auth = GoogleCalendarAuth(
                client_id=self._config.google_calendar_client_id,
                client_secret=self._config.google_calendar_client_secret,
                access_token=self._config.google_calendar_access_token,
                refresh_token=self._config.google_calendar_refresh_token,
            )
            config_path = Path(__file__).resolve().parent.parent.parent / "daily_plan_config.toml"
            calendar_context = load_calendar_context(config_path)

            self._context_sources.append(
                GoogleCalendarContextSource(
                    repository=GoogleCalendarRepository(auth),
                    calendar_context=calendar_context,
                    timezone=self._config.timezone,
                )
            )

    async def cog_load(self) -> None:
        """Called when the cog is loaded. Start the scheduler if configured."""
        if self._config.channel_id:
            self._schedule_loop.start()

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded. Stop the scheduler."""
        if self._schedule_loop.is_running():
            self._schedule_loop.cancel()

    @tasks.loop(hours=24)
    async def _schedule_loop(self) -> None:
        """Scheduled daily plan posting."""
        logger.info("Scheduled daily plan triggered")
        try:
            await self._generate_and_post()
        except Exception:
            logger.exception("Scheduled daily plan failed")

    @_schedule_loop.before_loop
    async def _before_schedule(self) -> None:
        """Wait until bot is ready, then wait until the scheduled time."""
        await self.bot.wait_until_ready()

        # Calculate time until next scheduled run
        tz = ZoneInfo(self._config.timezone)
        now = datetime.datetime.now(tz)
        scheduled_time = now.replace(
            hour=self._config.schedule_hour,
            minute=self._config.schedule_minute,
            second=0,
            microsecond=0,
        )

        # If scheduled time has passed today, wait until tomorrow
        if now >= scheduled_time:
            scheduled_time += datetime.timedelta(days=1)

        wait_seconds = (scheduled_time - now).total_seconds()
        logger.info(
            "Daily plan scheduled for %s (waiting %.0f seconds)",
            scheduled_time,
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)

    @app_commands.command(
        name="daily-plan",
        description="Generate today's plan from TickTick and GitHub tasks.",
    )
    @feature_enabled("daily-plan")
    async def daily_plan(self, interaction: Interaction) -> None:
        """Manual trigger for daily plan generation."""
        await interaction.response.defer()

        try:
            result_message = await self._generate_and_post()
            await interaction.followup.send(result_message)
        except Exception as e:
            logger.exception("Failed to generate daily plan")
            await interaction.followup.send(f"❌ Failed to generate daily plan: {e}")

    async def _generate_and_post(self) -> str:
        """Core logic: fetch tasks -> build prompt -> LLM -> post to thread.

        Returns a status message.
        """
        config = self._config
        tz = ZoneInfo(config.timezone)
        today = datetime.datetime.now(tz).date()
        date_str = today.strftime("%Y-%m-%d")
        thread_name = config.thread_format.format(date=date_str)

        # 1. Fetch from all sources concurrently
        task_coros = [source.fetch_and_format() for source in self._sources]
        context_coros = [source.fetch_and_format() for source in self._context_sources]

        all_results = await asyncio.gather(
            *task_coros, *context_coros, return_exceptions=True
        )

        # Separate task results and context results
        task_results_raw = all_results[: len(task_coros)]
        context_results_raw = all_results[len(task_coros) :]

        sections = []
        errors = []
        for i, result in enumerate(task_results_raw):
            if isinstance(result, Exception):
                source_name = self._sources[i].source_name
                logger.error("Source %s failed: %s", source_name, result)
                errors.append(source_name)
            else:
                sections.append(result)

        context_sections = []
        for i, result in enumerate(context_results_raw):
            if isinstance(result, Exception):
                source_name = self._context_sources[i].source_name
                logger.error("Context source %s failed: %s", source_name, result)
                errors.append(source_name)
            else:
                context_sections.append(result)

        if not sections and not errors:
            return "⚠ No task sources are configured. Set DAILY_PLAN_SOURCES and credentials."

        if not sections and errors:
            return f"❌ All task sources failed: {', '.join(errors)}"

        # 2. Find or create thread
        if not config.channel_id:
            return "⚠ DAILY_PLAN_CHANNEL_ID is not configured."

        channel = self.bot.get_channel(config.channel_id)
        if channel is None:
            return f"❌ Channel {config.channel_id} not found."

        thread = await self.discord_repo.find_or_create_thread(channel, thread_name)

        # 3. Fetch existing messages for context (2nd+ run)
        existing_messages = await self.discord_repo.fetch_thread_messages(thread)

        # 4. Build prompt and generate plan
        prompt = DailyPlanPromptBuilder.build_prompt(
            sections=sections,
            date_str=date_str,
            existing_messages=existing_messages if existing_messages else None,
            context_sections=context_sections if context_sections else None,
        )

        plan_text = await self.llm_repo.generate_content(prompt)

        # 5. Post to thread
        await self.discord_repo.send_to_thread(thread, plan_text)

        # 6. Build status message
        total_items = sum(s.item_count for s in sections)
        status = f"✅ Daily plan posted to {thread.mention} ({total_items} tasks"
        if errors:
            status += f", ⚠ failed sources: {', '.join(errors)}"
        status += ")"
        return status


async def setup(bot):
    await bot.add_cog(DailyPlanCog(bot))
