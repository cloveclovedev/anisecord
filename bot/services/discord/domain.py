from dataclasses import dataclass, field
from typing import List, Optional
import datetime

@dataclass(frozen=True)
class DiscordPost:
    """Class representing a single Discord message."""
    author_name: str
    content: str
    posted_at: datetime.datetime
    message_id: str
    thread_name: Optional[str] = None
    attachment_urls: List[str] = field(default_factory=list)
