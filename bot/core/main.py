import os
from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

from bot.core.health_server import start_health_server


class LifelogBot(commands.Bot):
    """Lifelog Discord Bot with Extension support."""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Bot configuration
        self.token = os.environ.get("DISCORD_BOT_TOKEN")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.port = int(os.environ.get("PORT", 8080))
        
        # Initialize bot
        intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=None, intents=intents)
    
    async def setup_hook(self):
        """Called when the bot is starting up. Load extensions here."""
        print("Setting up bot extensions...")
        
        # Load OSS extensions
        oss_extensions = [
            'bot.cogs.basic_commands',
            'bot.cogs.gemini_chat', 
            'bot.cogs.nutrition_coach'
        ]
        
        for extension in oss_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded extension: {extension}")
            except Exception as e:
                print(f"Failed to load extension {extension}: {e}")
        
        # Sync application commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} application commands.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
    
    async def on_ready(self):
        """Called when the bot is ready."""
        print(f'Logged in as: {self.user}')


def main():
    """Main entry point for the bot."""
    bot = LifelogBot()
    
    # Start health check server
    print(f"Starting health check server on port {bot.port}...")
    start_health_server(bot.port)
    
    try:
        # Start the Discord bot
        print("Starting Discord bot...")
        bot.run(bot.token)
    except Exception as e:
        print(f"Discord Bot encountered a fatal error: {e}")
    finally:
        print("Discord Bot is shutting down.")


if __name__ == "__main__":
    main()
