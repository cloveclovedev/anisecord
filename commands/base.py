from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseCommand(ABC):
    @abstractmethod
    def execute(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the command.

        Args:
            interaction_data (Dict[str, Any]): The data from the Discord interaction.

        Returns:
            Dict[str, Any]: The response to send back to Discord.
        """
        pass
