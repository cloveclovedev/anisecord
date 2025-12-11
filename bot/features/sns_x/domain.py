from dataclasses import dataclass
from typing import List
from bot.services.discord.domain import DiscordPost

@dataclass
class SnsXDraft:
    content: str
    source_posts_count: int

@dataclass
class SnsXConfig:
    user_id: str
    persona: str = "An official account for a solo developer. Professional yet friendly and engaging."

class SnsXDomain:
    @staticmethod
    def create_draft_prompt(messages: List[DiscordPost], persona: str, language: str = "ja") -> str:
        """
        Create the LLM prompt for generating an X post draft.
        """
        formatted_lines = []
        for msg in messages:
            # Format: [Time] User: Content
            # Note: Explicitly excluding attachments here as requested.
            base_info = f"[{msg.posted_at.strftime('%Y-%m-%d %H:%M')}] {msg.author_name}"
            
            if msg.thread_name:
                base_info += f" (in Thread: {msg.thread_name})"
                
            line = f"{base_info}: {msg.content}"
            formatted_lines.append(line)
        
        formatted_log = "\n".join(formatted_lines)
        
        prompt = f"""
You are a skilled social media manager. 
Create an engaging post for X (formerly Twitter) based on the following chat log from a Discord server.

**Persona Instructions:**
Act as: {persona}

The post should summarize the interesting parts of the conversation or highlight key activities.
Include relevant hashtags.

**IMPORTANT: Write the post in {language}.**

Chat Log:
{formatted_log}

Output format:
[Post Content]
        """
        return prompt
