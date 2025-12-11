from typing import List, Dict, Any, Union
import datetime
from services.discord import DiscordService
from services.llm import LLMService
from .domain import SnsXDomain, SnsXDraft, DiscordPost

class SnsXRepository:
    def __init__(self):
        self.discord_service = DiscordService()
        self.llm_service = LLMService()
        self.domain = SnsXDomain()

    def fetch_messages(self, channel_id: str, from_date: Union[datetime.date, datetime.datetime], to_date: Union[datetime.date, datetime.datetime]) -> List[DiscordPost]:
        """
        Fetches channel messages optimized with Snowflake ID 'after' parameter.
        Accepts date or datetime for precise control (e.g. Timezone support).
        """
        # Pass the from_date directly to service
        raw_messages = self.discord_service.fetch_channel_messages(channel_id, limit=100, after=from_date)
        
        # Convert raw dicts to Domain Objects (ACL)
        domain_posts = []
        for msg in raw_messages:
             timestamp_str = msg.get('timestamp')
             if not timestamp_str:
                 continue
             try:
                 # Check if dot exists for microseconds (Discord timestamps usually have them)
                 # 2023-10-10T12:00:00.000000+00:00
                 msg_date = datetime.datetime.fromisoformat(timestamp_str)
                 
                 # Extract attachment URLs
                 attachments = msg.get('attachments', [])
                 attachment_urls = [att.get('url') for att in attachments if att.get('url')]
                 
                 post = DiscordPost(
                     author_name=msg.get('author', {}).get('username', 'Unknown'),
                     content=msg.get('content', ''),
                     posted_at=msg_date,
                     message_id=msg.get('id', ''),
                     attachment_urls=attachment_urls
                 )
                 domain_posts.append(post)
             except ValueError:
                 continue

        # Further filtering to ensure we don't go past to_date and enforce exact date range
        return self.domain.filter_messages_by_date(domain_posts, from_date, to_date)

    def generate_draft(self, messages: List[DiscordPost]) -> SnsXDraft:
        """
        Generates an SNS draft from a list of messages using LLM.
        """
        if not messages:
            return SnsXDraft(content="No messages found in the specified range.", source_posts_count=0)

        # Format for LLM
        formatted_text = self.domain.format_messages_for_llm(messages)
        
        # Generate with LLM
        prompt = f"""
        Analyze the following Discord posts and extract work-related updates. 
        Create a draft post for X (formerly Twitter) summarizing these updates.
        
        Posts:
        {formatted_text}
        """
        draft_content = self.llm_service.generate_content(prompt)
        
        return SnsXDraft(content=draft_content, source_posts_count=len(messages))
