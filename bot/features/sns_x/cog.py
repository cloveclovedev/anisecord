from discord import Interaction, app_commands
from discord.ext import commands
import datetime
import zoneinfo

from bot.services.llm.repository import LLMRepository
from bot.services.discord.repository import DiscordRepository
from bot.core.user.decorators import feature_enabled
from bot.core.user.repository import UserRepository
from .domain import SnsXDomain, SnsXDraft
from .repository import SnsXConfigRepository

class SnsxCog(commands.Cog):
    """Generate X (Twitter) drafts from channel history."""

    def __init__(self, bot):
        self.bot = bot
        
        # Dependencies
        self.llm_repository = LLMRepository(
            model_name="gemini/gemini-2.5-flash",
            api_key=self.bot.gemini_api_key
        )
        self.discord_repository = DiscordRepository()
        self.user_repository = UserRepository()
        self.config_repository = SnsXConfigRepository()

    @app_commands.command(name="sns-x", description="Generate an X post draft from messages.")
    @feature_enabled("sns-x")
    @app_commands.describe(
        date_from="Start date (YYYY-MM-DD). Default: 24 hours ago.",
        date_to="End date (YYYY-MM-DD). Default: Now.",
        language="Output language (e.g. ja, en). Default: User setting."
    )
    async def sns_x(
        self, 
        interaction: Interaction, 
        date_from: str = None, 
        date_to: str = None,
        language: str = None
    ):
        """
        Generate an X post draft from messages in a specified range or last 24 hours.
        """
        await interaction.response.defer()

        try:
            # Get User Settings
            user = self.user_repository.get_user(str(interaction.user.id))
            # Get Feature Config
            config = self.config_repository.get_config(str(interaction.user.id))
            
            tz = zoneinfo.ZoneInfo(user.timezone)
            target_lang = language or user.language

            # Determine Time Range
            now = datetime.datetime.now(tz)
            
            # Default: Last 24 hours (UTC calculation safe, but better to be explicit)
            start_dt = None
            end_dt = None

            if date_from:
                try:
                    # Parse YYYY-MM-DD in User's Timezone
                    d_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
                    # Start of that day
                    start_dt = datetime.datetime.combine(d_from, datetime.time.min, tzinfo=tz)
                except ValueError:
                    await interaction.followup.send("❌ Invalid date_from format. Use YYYY-MM-DD.")
                    return
            else:
                # Default to 24 hours ago from now
                start_dt = now - datetime.timedelta(hours=24)

            if date_to:
                try:
                    d_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
                    # End of that day (or start of next day?) Usually users expect inclusive. 
                    # Let's set it to end of day 23:59:59
                    end_dt = datetime.datetime.combine(d_to, datetime.time.max, tzinfo=tz)
                except ValueError:
                    await interaction.followup.send("❌ Invalid date_to format. Use YYYY-MM-DD.")
                    return
            else:
                # Default to Now
                end_dt = now

            # Message
            time_range_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%Y-%m-%d %H:%M')} ({user.timezone})"
            print(f"Fetching messages for {time_range_str}")

            # Fetch messages
            messages = await self.discord_repository.fetch_messages(
                channel=interaction.channel, 
                after=start_dt,
                before=end_dt
            )
            
            if not messages:
                await interaction.followup.send(f"**X Post Draft**\nTime: {time_range_str}\n\nNo messages found in this period.")
                return

            # Generate draft
            prompt = SnsXDomain.create_draft_prompt(messages, persona=config.persona, language=target_lang)
            content = await self.llm_repository.generate_content(prompt)
            draft = SnsXDraft(content=content, source_posts_count=len(messages))
            
            response_text = f"**X Post Draft ({target_lang})**\nTime: {time_range_str}\nMessages: {draft.source_posts_count}\n\n{draft.content}"
            if len(response_text) > 2000:
                response_text = response_text[:1900] + "\n...(truncated)"
                
            await interaction.followup.send(response_text)
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}")

    @app_commands.command(name="sns-x-today", description="Generate an X post draft for today's messages.")
    @feature_enabled("sns-x")
    @app_commands.describe(
        language="Output language (e.g. ja, en). Default: User setting."
    )
    async def sns_x_today(self, interaction: Interaction, language: str = None):
        """
        Generate an X post draft from messages posted "Today" (User Timezone).
        """
        await interaction.response.defer()

        try:
            user = self.user_repository.get_user(str(interaction.user.id))
            # Get Feature Config
            config = self.config_repository.get_config(str(interaction.user.id))

            tz = zoneinfo.ZoneInfo(user.timezone)
            target_lang = language or user.language

            # "Today" means from 00:00 (User TZ) to Now
            now = datetime.datetime.now(tz)
            start_dt = datetime.datetime.combine(now.date(), datetime.time.min, tzinfo=tz)
            end_dt = now

            time_range_str = f"{start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%Y-%m-%d %H:%M')} ({user.timezone})"
            print(f"Fetching messages for {time_range_str} (Today)")

            messages = await self.discord_repository.fetch_messages(
                channel=interaction.channel, 
                after=start_dt,
                before=end_dt
            )
            
            if not messages:
                await interaction.followup.send(f"**X Post Draft (Today)**\nTime: {time_range_str}\n\nNo messages found today.")
                return

            # Generate draft
            prompt = SnsXDomain.create_draft_prompt(messages, persona=config.persona, language=target_lang)
            content = await self.llm_repository.generate_content(prompt)
            draft = SnsXDraft(content=content, source_posts_count=len(messages))
            
            response_text = f"**X Post Draft (Today, {target_lang})**\nTime: {time_range_str}\nMessages: {draft.source_posts_count}\n\n{draft.content}"
            if len(response_text) > 2000:
                response_text = response_text[:1900] + "\n...(truncated)"
                
            await interaction.followup.send(response_text)
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}")

async def setup(bot):
    await bot.add_cog(SnsxCog(bot))
