import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    print("Error: ANTHROPIC_API_KEY is not set. Add it to your .env file.")
    raise SystemExit(1)

import anthropic

client = anthropic.Anthropic(api_key=api_key)

try:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
    )
    print(message.content[0].text)
except anthropic.AuthenticationError:
    print("Error: ANTHROPIC_API_KEY is invalid or unauthorized.")
except Exception as e:
    print(f"Error calling Anthropic API: {e}")
