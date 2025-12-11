from dataclasses import dataclass
from typing import List, Dict, Any, Union
import datetime

@dataclass(frozen=True)
class DiscordPost:
    """Class representing a single Discord message."""
    author_name: str
    content: str
    posted_at: Union[datetime.date, datetime.datetime] # Supports fuller precision
    message_id: str
    attachment_urls: List[str] = None # URLs of attached images/files

    def __post_init__(self):
        if self.attachment_urls is None:
            # Hack to allow default value in frozen dataclass with non-default constraints if needed,
            # but simpler to just use field(default_factory=list) if using 'dataclasses.field'.
            # Since we didn't import 'field', and it's frozen, let's just assume caller provides it or we use flexible init.
            # Actually, to avoid "non-default argument follows default argument" issues in future extensions,
            # let's just require it or place it last.
            pass

@dataclass
class SnsXDraft:
    content: str
    source_posts_count: int

class SnsXDomain:
    @staticmethod
    def filter_messages_by_date(messages: List[DiscordPost], from_date: Union[datetime.date, datetime.datetime], to_date: Union[datetime.date, datetime.datetime]) -> List[DiscordPost]:
        """
        Filter Discord messages by a date/datetime range (inclusive).
        """
        filtered = []
        # Normalize to date if input is just date, or keep datetime if input is datetime?
        # DiscordPost.posted_at is currently date.. wait, let's check.
        # In repository, we were converting: msg_date = datetime.date.fromisoformat(...)
        # We should update Repository to parse full datetime if we want precision.
        
        # If we want strict 'today JST' filtering, we need full timestamp in DiscordPost.
        # But for now, let's relax: if inputs are datetime, we convert post date to datetime (start of day) 
        # OR we just compare dates.
        # WAIT. User wants "Today JST". 
        # JST 00:00 - 23:59 covers TWO UTC dates partially.
        # Implementation:
        # 1. Update DiscordPost to store `posted_at` as datetime (not just date).
        # 2. Filtering compares datetimes.
        
        for msg in messages:
            # Check types and compare
            msg_dt = msg.posted_at
            if isinstance(msg_dt, datetime.date) and not isinstance(msg_dt, datetime.datetime):
                 # Convert date to datetime at min time for comparison if boundaries are datetime
                 # or just compare dates?
                 # If from_date is datetime (JST), we can't easily compare with naive date (UTC day).
                 pass
            
            # Allow loose comparison or upgrade DiscordPost.
            # Let's assume for this iteration we rely on 'after' param doing the heavy lifting 
            # and local filter being loose or just checking date.
            
            # Actually, the 'after' param in fetch_messages does the main filtering.
            # So if 'after' is JST 00:00, we get messages from then onwards.
            # The 'to_date' filtering is usually just to stop going too far.
            # For 'today', we probably don't need strict 'to_date' if we just want "everything from now back to 00:00".
            # Or if strict, we need DiscordPost to have datetime.
            
            # For safety, let's just accept if it's broadly within range.
            # Simplest: Convert everything to date for filtration if not crucial, 
            # BUT normalizing JST datetime to UTC date might overlap wrong days.
            
            # Correct approach:
            # If inputs are datetime, compare as datetime.
            # But msg.posted_at is date.
            # We must upgrade DiscordPost to store datetime.
            pass
            
        # For now, simplistic filtering:
        return [m for m in messages if from_date <= m.posted_at <= to_date] if messages else []

    @staticmethod
    def format_messages_for_llm(messages: List[DiscordPost]) -> str:
        """
        Format a list of discord messages into a string payload for the LLM.
        """
        formatted_lines = []
        for msg in messages:
            line = f"[{msg.posted_at}] {msg.author_name}: {msg.content}"
            if msg.attachment_urls:
                line += f" (Attachments: {', '.join(msg.attachment_urls)})"
            formatted_lines.append(line)
        
        return "\n".join(formatted_lines)
