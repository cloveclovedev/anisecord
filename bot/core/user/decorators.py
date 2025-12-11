from discord import Interaction, app_commands
from discord.ext import commands
from .repository import UserRepository

class FeatureAccessDenied(app_commands.CheckFailure):
    """Exception raised when a user does not have access to a feature."""
    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        super().__init__(f"Access denied for feature: {feature_name}")

async def handle_permission_error(interaction: Interaction, error: app_commands.AppCommandError):
    """
    Handle permission errors (FeatureAccessDenied) from feature_enabled decorator.
    """
    if isinstance(error, FeatureAccessDenied):
        await interaction.response.send_message(
            f"🚫 **Access Denied**: You do not have permission to use the `{error.feature_name}` feature.", 
            ephemeral=True
        )
        return True # Handled
    return False # Not handled

def feature_enabled(feature_name: str):
    """
    Decorator to check if a feature is enabled for the user.
    """
    async def predicate(interaction: Interaction) -> bool:
        # NOTE: app_commands.check predicate receives Interaction, not Context
        repo = UserRepository()
        
        user_id = str(interaction.user.id)
        user = repo.get_user(user_id)
        
        if feature_name in user.allowed_features:
            return True
        
        # Raise specific exception instead of returning False
        raise FeatureAccessDenied(feature_name)
        
    return app_commands.check(predicate)
