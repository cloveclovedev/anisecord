import os
from litellm import completion

class LLMService:
    def __init__(self, model_name: str = "gemini/gemini-pro"):
        """
        Initialize the LLM Service.
        
        Args:
            model_name (str): The model identifier for litellm. 
                              Default is 'gemini/gemini-pro'.
                              Can be changed to 'gpt-4', 'claude-3-opus', etc.
        """
        self.model_name = model_name
        # litellm requires API keys to be set in environment variables
        # e.g. GEMINI_API_KEY, OPENAI_API_KEY, etc.

    def generate_content(self, prompt: str) -> str:
        """
        Generate content using the configured LLM.

        Args:
            prompt (str): The prompt to send to the LLM.

        Returns:
            str: The generated response text.
        """
        try:
            response = completion(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}]
            )
            # litellm response structure is similar to OpenAI's
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error generating content: {e}")
            return "Warp drive malfunction! Could not generate response."
