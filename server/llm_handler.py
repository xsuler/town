import os
import asyncio
import json
from json_repair import repair_json
import httpx
from shared.config import OPENAI_API_KEY

class LLMHandler:
    def __init__(self, api_key: str = "xx", api_base: str = "http://localhost:11434/v1", model: str = "phi4"):
        self.api_key = api_key
        self.api_base = api_base.rstrip('/')  # Ensure no trailing slash
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=self.api_base,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            timeout=60.0  # Adjust timeout as needed
        )

    async def get_response(self, messages, max_tokens=150, json=True):
        if isinstance(messages, str):
            messages = [
                {"role": "system", "content": "You are a helpful assistant. Respond with a JSON object."},
                {"role": "user", "content": messages}
            ]

        payload = {
            "model": self.model,
            "messages": messages,
            "n": 1,
            "stop": None,
            "temperature": 0.7,
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        except httpx.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except KeyError as key_err:
            print(f"Unexpected response structure: {key_err}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return ""

    async def get_action(self, prompt):
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Respond with a JSON object."},
            {"role": "user", "content": prompt}
        ]

        response = await self.get_response(messages)
        if not response:
            print("No response received from LLM.")
            return {"type": "rest"}  # Default action

        try:
            # Attempt to parse JSON
            action = json.loads(repair_json(response))
            return action
        except json.JSONDecodeError:
            # If JSON parsing fails, default to 'rest' or handle accordingly
            print(f"Failed to parse LLM response: {response}")
            return {"type": "rest"}  # Default action

    async def close(self):
        await self.client.aclose()
