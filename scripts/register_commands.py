import os
import requests
import json
import argparse
from dotenv import load_dotenv

# Load .env from project root
load_dotenv()

def register_commands(app_id: str, bot_token: str, guild_id: str = None):
    url = f"https://discord.com/api/v10/applications/{app_id}/commands"
    if guild_id:
        url = f"https://discord.com/api/v10/applications/{app_id}/guilds/{guild_id}/commands"
    
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    commands = [
        {
            "name": "sns-x",
            "description": "Generate SNS draft from Discord messages",
            "type": 1, # CHAT_INPUT
            "options": [
                {
                    "name": "from",
                    "description": "Start date (YYYY-MM-DD)",
                    "type": 3, # STRING
                    "required": True
                },
                {
                    "name": "to",
                    "description": "End date (YYYY-MM-DD)",
                    "type": 3, # STRING
                    "required": True
                }
            ]
        },
        {
            "name": "sns-x-today",
            "description": "Generate SNS draft for today's updates (JST)",
            "type": 1, # CHAT_INPUT
            "options": [] # No options needed
        }
    ]

    for command in commands:
        response = requests.post(url, headers=headers, json=command)
        if response.status_code in [200, 201]:
            print(f"Successfully registered command: {command['name']}")
        else:
            print(f"Failed to register command {command['name']}: {response.status_code} {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register Discord Slash Commands")
    parser.add_argument("--app-id", help="Discord Application ID", required=False)
    parser.add_argument("--token", help="Discord Bot Token", required=False)
    parser.add_argument("--guild-id", help="Guild ID (for instant update)", required=False)

    args = parser.parse_args()

    # Prefer env vars if args not provided
    app_id = args.app_id or os.environ.get("DISCORD_APPLICATION_ID")
    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    
    # Optional Guild ID
    guild_id = args.guild_id or os.environ.get("DISCORD_GUILD_ID")

    if not app_id or not token:
        print("Error: DISCORD_APPLICATION_ID and DISCORD_BOT_TOKEN must be provided via arguments or environment variables.")
        exit(1)

    register_commands(app_id, token, guild_id)
