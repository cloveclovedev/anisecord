import litellm
from typing import Union, List, Dict, Any

class LLMRepository:
    def __init__(self, model_name: str, api_key: str):
        """
        Initialize the LLM Repository.
        
        Args:
            model_name (str): The model identifier for litellm (e.g. 'gemini/gemini-2.5-flash').
            api_key (str): The API key for the LLM provider.
        """
        self.model_name = model_name
        self.api_key = api_key

    async def generate_content(self, input_content: Union[str, List[Dict[str, Any]]]) -> str:
        """
        Generate content using the configured LLM.

        Args:
            input_content (Union[str, List[Dict[str, Any]]]): The prompt (string) or complex content (list of dicts) to send.

        Returns:
            str: The generated response text.
        """
        try:
            # Wrap string prompt in list of dicts for litellm consistency if needed, 
            # but litellm handles string prompt too. 
            # However, for consistency with 'messages' format:
            messages = [{"role": "user", "content": input_content}]
            
            response = await litellm.acompletion(
                model=self.model_name,
                messages=messages,
                api_key=self.api_key,
                num_retries=3  # Retry on 503/Overload errors
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating content via LLMRepository: {e}")
            raise
