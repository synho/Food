from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client()

print("Available models:")
for model in client.models.list():
    print(f"- {model.name} (supports: {model.supported_actions})")
