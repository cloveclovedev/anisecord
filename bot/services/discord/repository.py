import discord
import datetime
from typing import List, Optional
from .domain import DiscordPost

class DiscordRepository:
    async def fetch_messages(
        self, 
        channel: discord.TextChannel, 
        after: datetime.datetime, 
        before: Optional[datetime.datetime] = None,
        limit: int = 2000
    ) -> List[DiscordPost]:
        """
        Fetch messages from a Discord channel history within a date range.
        
        Args:
            channel: The text channel to fetch from.
            after: Fetch messages after this datetime (oldest limit).
            before: Fetch messages before this datetime (newest limit). If None, fetches up to now.
            limit: Max messages to fetch. Discord API defaults to 100 per request, library handles pagination.
        """
        posts = []
        
        # 1. Fetch from Main Channel
        async for msg in channel.history(limit=limit, after=after, before=before, oldest_first=True):
            if msg.author.bot:
                continue
            posts.append(self._to_discord_post(msg))

        # 2. Identify Threads to check (Active + Archived)
        threads_to_check = list(channel.threads) # Active threads
        
        # Add archived threads modified after start time
        try:
             async for thread in channel.archived_threads(after=after):
                 threads_to_check.append(thread)
        except Exception as e:
            print(f"Failed to fetch archived threads: {e}")

        # 3. Fetch from Threads
        for thread in threads_to_check:
            # We use the same time range for threads
            try:
                async for msg in thread.history(limit=limit, after=after, before=before, oldest_first=True):
                    if msg.author.bot:
                        continue
                    posts.append(self._to_discord_post(msg, thread_name=thread.name))
            except discord.Forbidden:
                continue # Skip threads we can't read
            except Exception as e:
                print(f"Error reading thread {thread.name}: {e}")

        # 4. Sort by time (oldest first)
        posts.sort(key=lambda p: p.posted_at)
        
        return posts

    def _to_discord_post(self, msg: discord.Message, thread_name: str = None) -> DiscordPost:
        """Helper to convert discord.Message to DiscordPost."""
        content = msg.content
            
        attachment_urls = [a.url for a in msg.attachments]
            
        return DiscordPost(
            author_name=msg.author.display_name,
            content=content,
            posted_at=msg.created_at,
            message_id=str(msg.id),
            thread_name=thread_name,
            attachment_urls=attachment_urls
        )
