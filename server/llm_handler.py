import openai
from shared.config import OPENAI_API_KEY
import asyncio
import json
from json_repair import repair_json

openai.api_key = OPENAI_API_KEY
openai.api_base = "http://localhost:11434/v1"

class LLMHandler:
    def __init__(self):
        pass

    async def get_response(self, messages, max_tokens=150, json=True):
        if isinstance(messages, str):
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Respond with a JSON object."},
                {"role": "user", "content": messages}
                ]
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: openai.ChatCompletion.create(
                    model="phi4",  # Replace with your chat model name
                    messages=messages,
                    n=1,
                    stop=None,
                    temperature=0.7,
                )
            )
            return response.choices[0].message['content'].strip()
        except Exception as e:
            print(f"LLM Error: {e}")
            return ""

    async def get_action(self, prompt):
        # Define messages for the chat interface
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Respond with a JSON object."},
            {"role": "user", "content": prompt}
        ]

        response = await self.get_response(messages)
        try:
            # Attempt to parse JSON
            action = json.loads(repair_json(response))
            return action
        except json.JSONDecodeError:
            # If JSON parsing fails, default to 'rest' or handle accordingly
            print(f"Failed to parse LLM response: {response}")
            return {"type": "rest"}  # Default action
