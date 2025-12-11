import traceback
from discord import Interaction, app_commands
from discord.ext import commands

from bot.utils.gemini_helpers import call_gemini_api


class GeminiChatCog(commands.Cog):
    """Gemini AI chat functionality."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="hello", description="Send a prompt to Gemini API.")
    @app_commands.describe(prompt="Message to send to the API")
    async def hello(self, interaction: Interaction, prompt: str):
        """Send a prompt to Gemini API and get response."""
        # Defer response to prevent timeout
        await interaction.response.defer()

        try:
            print(f"Calling Gemini API with prompt: {prompt}")
            response_text = await call_gemini_api(
                content=prompt,
                api_key=self.bot.gemini_api_key
            )
            print(f"Received response from Gemini: {response_text[:100]}...")

        except Exception as e:
            print("An error occurred with the Gemini API call.")
            traceback.print_exc()
            await interaction.followup.send("An error occurred while calling the API. Please try again later.")
            return

        await interaction.followup.send(f"**Your prompt:**\n> {prompt}\n\n**Gemini response:**\n{response_text}")


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(GeminiChatCog(bot))

