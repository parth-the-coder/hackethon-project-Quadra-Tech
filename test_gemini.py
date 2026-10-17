
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "").strip()

if not api_key:
    print("ERROR: Gemini API key not found")
else:
    try:
        client = genai.Client(api_key=api_key)

        response = client.interactions.create(
            model="gemini-3.8-flash",
            input="Reply with: OpsPilot Gemini is working!"
        )

        print("SUCCESS:", response.output_text)

    except Exception as e:
        print("ERROR:", type(e).__name__, str(e))
