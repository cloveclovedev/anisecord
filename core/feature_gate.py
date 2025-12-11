import os

class FeatureGate:
    def __init__(self):
        # In the future, this could be loaded from a database or config file
        pass

    def is_enabled(self, feature_name: str, user_id: str) -> bool:
        """
        Check if a feature is enabled for a given user.
        
        Args:
            feature_name (str): The name of the feature to check.
            user_id (str): The Discord user ID.
            
        Returns:
            bool: True if the feature is enabled, False otherwise.
        """
        # TODO: Implement actual logic. For now, everything is open.
        return True
