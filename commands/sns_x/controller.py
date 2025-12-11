from typing import Dict, Any, Optional
import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.9+ has zoneinfo built-in
    # For older versions, backports.zoneinfo is needed
    raise ImportError("Python 3.9+ with zoneinfo module is required.")
            
from core.feature_gate import FeatureGate
from core.user.repository import UserRepository
from commands.base import BaseCommand
from .repository import SnsXRepository

class SnsXTodayController:
    def __init__(self):
        self.feature_gate = FeatureGate()
        self.repository = SnsXRepository()
        self.user_repository = UserRepository()

    def execute(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        user_id = interaction_data.get('member', {}).get('user', {}).get('id')
        
        # 1. Feature Gate Check
        if not self.feature_gate.is_enabled('sns-x', user_id):
             return {
                'type': 4,
                'data': {'content': 'This feature is currently disabled for you.'}
            }
            
        # 2. Get User Timezone
        user = self.user_repository.get_user(user_id)
        tz_name = user.timezone
        
        try:
            tz = ZoneInfo(tz_name)
        except Exception as e:
            print(f"Warning: Invalid timezone '{tz_name}' for user {user_id}: {e}. Defaulting to UTC.")
            tz = datetime.timezone.utc

        # 3. Calculate Today Range
        now = datetime.datetime.now(tz)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # 4. Fetch Messages
        # Get channel from interaction
        channel_id = interaction_data.get('channel_id')
        if not channel_id:
             return {'type': 4, 'data': {'content': 'Could not determine channel ID.'}}

        # Note: repository expects date objects for range filter, 
        # but fetch_messages now uses discord_service which handles datetime for 'after'.
        # However, repository signature is (channel_id, from_date: date, to_date: date).
        # We should update repository signature or just pass dates?
        # If we pass dates, we lose the exact time (00:00 vs current time).
        # But 'today' usually means 'start of today'.
        # Let's verify repository method signature.
        # It takes datetime.date.
        # If we pass today_start.date(), it means YYYY-MM-DD.
        
        # SnsXRepository.fetch_messages signature: 
        # (channel_id: str, from_date: datetime.date, to_date: datetime.date)
        
        # Wait, if we use repository.fetch_messages, it passes from_date as 'after'.
        # discord_service.date_to_snowflake(date) -> 00:00 UTC of that date.
        # If we want 00:00 JST, we must pass datetime to discord service.
        # But repository takes 'date'.
        
        # We need to enhance Repository to accept datetime OR generic date.
        # For now, let's pass .date() and accept that snowflake might be slightly off (UTC) 
        # OR we modify Repository to accept datetime.
        
        # Given "today" command requirement (JST support), we MUST fix Repository to accept datetime 
        # or handle the logic correctly. 
        # The user specifically requested JST. 00:00 JST != 00:00 UTC.
        # 00:00 JST is previous day 15:00 UTC.
        
        # If I pass the date "2023-12-11" (which is today JST), to 'date_to_snowflake',
        # it converts to "2023-12-11 00:00:00 UTC".
        # This is 9 hours AHEAD of JST 00:00.
        # So I would miss the first 9 hours of JST messages.
        
        # This confirms Repository MUST be updated or bypassed.
        # Let's assume for this step I will update Repository signature too?
        # Or I can just pass the datetime object if type hint is loose/ignored at runtime?
        # Python filters at runtime using 'filter_messages_by_date'.
        
        # Quick fix: Update Repository to accept Union[date, datetime] and forward it.
        # I will do that in next step.
        
        messages = self.repository.fetch_messages(channel_id, today_start, today_end)
        
        # 5. Generate Draft
        draft = self.repository.generate_draft(messages)

        return {
            'type': 4,
            'data': {'content': f"Here is your X post draft for Today ({draft.source_posts_count} posts):\n\n{draft.content}"}
        }

class SnsXController(BaseCommand):
    def __init__(self):
        self.feature_gate = FeatureGate()
        self.repository = SnsXRepository()
        self.user_repository = UserRepository()

    def execute(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Entry point for /sns-x command.
        """
        # 1. Feature Gate Check
        user_id = interaction_data.get('member', {}).get('user', {}).get('id')
        if not self.feature_gate.is_enabled('sns-x', user_id):
             return {
                'type': 4,
                'data': {'content': 'This feature is currently disabled for you.'}
            }

        # 2. Parse Options
        options = interaction_data.get('data', {}).get('options', [])
        from_str = next((opt['value'] for opt in options if opt['name'] == 'from'), None)
        to_str = next((opt['value'] for opt in options if opt['name'] == 'to'), None)
        
        # Channel ID is in the interaction data
        channel_id = interaction_data.get('channel_id')

        if not from_str or not to_str:
             return {
                'type': 4,
                'data': {'content': 'Please provide both start and end dates.'}
            }

        # Resolve Timezone
        user = self.user_repository.get_user(user_id)
        try:
            tz = ZoneInfo(user.timezone)
        except Exception as e:
            print(f"Warning: Invalid timezone '{user.timezone}' for user {user_id}: {e}. Defaulting to UTC.")
            tz = datetime.timezone.utc

        try:
            from_date_raw = datetime.date.fromisoformat(from_str)
            to_date_raw = datetime.date.fromisoformat(to_str)
            
            # Convert to datetime range in User's Timezone
            from_date = datetime.datetime.combine(from_date_raw, datetime.time.min, tzinfo=tz)
            to_date = datetime.datetime.combine(to_date_raw, datetime.time.max, tzinfo=tz)

        except ValueError:
            return {
                'type': 4,
                'data': {'content': 'Invalid date format. Please use YYYY-MM-DD.'}
            }

        # 3. Call Repository
        # Step A: Fetch messages
        messages = self.repository.fetch_messages(channel_id, from_date, to_date)
        
        # Step B: Generate Draft
        draft = self.repository.generate_draft(messages)

        # 4. Return Response
        return {
            'type': 4,
            'data': {'content': f"Here is your X post draft (based on {draft.source_posts_count} posts):\n\n{draft.content}"}
        }
