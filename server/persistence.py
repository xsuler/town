import json
from datetime import datetime

class Persistence:
    def __init__(self, s):
        self.world_summary = []
        self.agents = {}
        self.users = {}
        self.events = []
        self.economy = []
        self.weather = []
        self.agent_memories = []

    async def initialize(self):
        # No need to create tables in an in-memory store
        pass

    async def save_world_summary(self, summary):
        self.world_summary.append({
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        })

    async def get_latest_world_summary(self):
        if self.world_summary:
            return self.world_summary[-1]["summary"]
        return "No summary available."

    async def add_agent(self, name, role, background, personality, position_x, position_y, relationships):
        self.agents[name] = {
            "role": role,
            "background": background,
            "personality": personality,
            "position_x": position_x,
            "position_y": position_y,
            "relationships": relationships
        }

    async def add_user(self, name, background, position_x, position_y):
        self.users[name] = {
            "background": background,
            "position_x": position_x,
            "position_y": position_y
        }

    async def add_event(self, description):
        print(description)
        self.events.append({
            "description": description,
            "timestamp": datetime.now().isoformat()
        })

    async def get_events(self):
        return [{"description": event["description"], "timestamp": event["timestamp"]} for event in self.events]

    async def save_economy(self, resources):
        self.economy.append({
            "resources": json.dumps(resources),
            "timestamp": datetime.now().isoformat()
        })

    async def get_latest_economy(self):
        if self.economy:
            return json.loads(self.economy[-1]["resources"])
        return {}

    async def save_weather(self, current_weather):
        self.weather.append({
            "current_weather": current_weather,
            "timestamp": datetime.now().isoformat()
        })

    async def get_latest_weather(self):
        if self.weather:
            return self.weather[-1]["current_weather"]
        return "Sunny"

    async def add_agent_memory(self, agent_name, memory):
        self.agent_memories.append({
            "agent_name": agent_name,
            "memory": memory,
            "timestamp": datetime.now().isoformat()
        })

    async def get_agent_memories(self, agent_name):
        return [{"memory": memory["memory"], "timestamp": memory["timestamp"]}
                for memory in self.agent_memories if memory["agent_name"] == agent_name]

# Example usage:
# store = InMemoryStore()
# await store.initialize()
# await store.save_world_summary("This is a summary of the world.")
# print(await store.get_latest_world_summary())