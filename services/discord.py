import requests
import os
import datetime
from typing import List, Dict, Any, Optional, Union

class DiscordService:
    def __init__(self, bot_token: Optional[str] = None):
        self.base_url = "https://discord.com/api/v10"
        # In a real deployed environment, DISCORD_BOT_TOKEN would be in env vars
        self.bot_token = bot_token or os.environ.get('DISCORD_BOT_TOKEN')

    @staticmethod
    def date_to_snowflake(date_obj: Union[datetime.date, datetime.datetime]) -> str:
        """
        Convert a date or datetime object to a Discord Snowflake ID.
        Unix Timestamp (ms) - Discord Epoch (1420070400000) << 22
        """
        if isinstance(date_obj, datetime.datetime):
            dt = date_obj
            # If naive, assume UTC to be safe, though ideally should be aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=datetime.timezone.utc)
        else:
            # It's a date, assume start of day UTC
            dt = datetime.datetime.combine(date_obj, datetime.time.min, tzinfo=datetime.timezone.utc)
            
        timestamp = int(dt.timestamp() * 1000)
        discord_epoch = 1420070400000
        return str((timestamp - discord_epoch) << 22)

    def fetch_channel_messages(self, channel_id: str, limit: int = 100, after: Optional[Union[str, datetime.date, datetime.datetime]] = None, before: Optional[Union[str, datetime.date, datetime.datetime]] = None) -> List[Dict[str, Any]]:
        """
        Fetch messages from a specific Discord channel.

        Args:
            channel_id (str): The ID of the channel to fetch messages from.
            limit (int): Number of messages to fetch (max 100).
            after (Union[str, datetime.date]): Get messages after this message ID or Date.
            before (Union[str, datetime.date]): Get messages before this message ID or Date.

        Returns:
            List[Dict[str, Any]]: A list of message objects.
        """
        if not self.bot_token:
            print("Warning: DISCORD_BOT_TOKEN is not set. Returning empty list.")
            return []

        headers = {
            "Authorization": f"Bot {self.bot_token}",
            "Content-Type": "application/json"
        }
        
        params = {'limit': limit}
        
        if after:
            if isinstance(after, (datetime.date, datetime.datetime)):
                params['after'] = self.date_to_snowflake(after)
            else:
                params['after'] = after
                
        if before:
            if isinstance(before, (datetime.date, datetime.datetime)):
                params['before'] = self.date_to_snowflake(before)
            else:
                params['before'] = before

        url = f"{self.base_url}/channels/{channel_id}/messages"
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Discord messages: {e}")
            return []
