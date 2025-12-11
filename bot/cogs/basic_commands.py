from discord import Interaction, app_commands
from discord.ext import commands


class BasicCommandsCog(commands.Cog):
    """Basic utility commands."""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Test bot response time.")
    async def ping(self, interaction: Interaction):
        """Test bot response time."""
        await interaction.response.send_message(f'Pong! ({round(self.bot.latency * 1000)}ms)')


async def setup(bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(BasicCommandsCog(bot))

