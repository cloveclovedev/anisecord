import os
import sys
# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from services.llm import LLMService

# Load .env
load_dotenv()

def test_llm():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        print("Please ensure .env file exists and contains the key.")
        return

    print("Initializing LLMService...")
    # This will use the default model defined in LLMService (gemini-2.5-flash as per user change)
    llm = LLMService(model_name="gemini/gemini-2.5-flash")
    print(f"Model: {llm.model_name}")

    print("Sending test prompt...")
    try:
        response = llm.generate_content("Hello! Are you operational? Please reply with 'Yes'.")
        print(f"\nResponse from AI:\n{response}")
        print("\nSUCCESS: LLM connection verified.")
    except Exception as e:
        print(f"\nFAILURE: LLM verification failed.\nError: {e}")

if __name__ == "__main__":
    test_llm()
