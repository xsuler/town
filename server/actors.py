import ray
import asyncio
from llm_handler import LLMHandler
from persistence import Persistence
from shared.config import DATABASE_PATH
import json
import random

@ray.remote
class World:
    def __init__(self):
        self.llm = LLMHandler()
        self.persistence = Persistence(DATABASE_PATH)
        self.world_summary = ""
        self.agents = {}
        self.users = {}

    async def get_agents(self):
        return self.agents

    async def update_world_summary(self, summary):
        self.world_summary = summary
        await self.persistence.save_world_summary(json.dumps(summary))

    async def get_world_summary(self, requester_name):
        return self.world_summary

    async def register_agent(self, name, role, background, personality, position):
        self.agents[name] = {
            "role": role,
            "background": background,
            "personality": personality,
            "position": position,
            "relationships": {}
        }
        print(self.agents)
        await self.persistence.add_agent(
            name, role, background, personality, position[0], position[1], json.dumps(self.agents[name]["relationships"])
        )

    async def register_user(self, name, background, position):
        self.users[name] = {
            "background": background,
            "position": position
        }
        await self.persistence.add_user(
            name, background, position[0], position[1]
        )

    async def broadcast_event(self, description):
        await self.persistence.add_event(description)

    async def get_state(self):
        return {
            "agents": self.agents,
            "users": self.users,
            "world_summary": self.world_summary,
        }


    async def get_persistence(self):
        return self.persistence

@ray.remote
class Supervisor:
    def __init__(self, world):
        self.world = world
        self.llm = LLMHandler()

    async def monitor_systems(self):
        while True:
            await self.generate_and_upload_summary()
            await asyncio.sleep(1)  # Run every 60 seconds


    async def generate_and_upload_summary(self):
        context = await self.get_context()
        summary = await self.generate_summary(context)
        await self.world.update_world_summary.remote(summary)

    async def get_context(self):
        state = await self.world.get_state.remote()
        return json.dumps(state, indent=2)

    async def generate_summary(self, context):
        prompt = f"""Provide a concise summary of the following world state:\n{context}, return json: {{"summary"': summary}}"""
        summary = await self.llm.get_response(prompt, max_tokens=150)
        return summary

@ray.remote
class EventBoard:
    def __init__(self, world):
        self.world = world

    async def generate_events(self):
        self.llm = LLMHandler()
        while True:
            context = await self.get_context()
            prompt = f"Generate a dynamic and engaging event that fits within the following world context:\n{context}"
            event = await self.llm.get_response(prompt, max_tokens=100, json=False)
            if event:
                await self.world.broadcast_event.remote(event)
            await asyncio.sleep(random.randint(1, 2))  # Random interval between events

    async def get_context(self):
        state = await self.world.get_state.remote()
        return json.dumps(state, indent=2)

@ray.remote
class Agent:
    def __init__(self, name, role, background, personality, position, world):
        self.name = name
        self.role = role
        self.background = background
        self.personality = personality
        self.position = position
        self.world = world
        self.llm = LLMHandler()

    async def register(self):
        await self.world.register_agent.remote(
            self.name, self.role, self.background, self.personality, self.position
        )
        await self.initialize_memory()

    async def initialize_memory(self):
        initial_memory = f"{self.name} has joined the simulation."
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, initial_memory)

    async def decide_action(self):
        context = await self.get_context()
        prompt = self.generate_prompt(context)
        print(prompt)
        action = await self.llm.get_action(prompt)
        print(action)
        if isinstance(action, list):
            for a in action:
                await self.execute_action(a)

    def generate_prompt(self, context):
        memory_snippet = self.get_memory_snippet()
        return f"""
You are {self.name}, a {self.role} with a {self.personality} personality.
Background: {self.background}
Memories:
{memory_snippet}
World Context:
{context}
Decide your next action and respond in JSON format:
{{
  "type": "move" | "talk" | "rest" | "perform_task" | "evolve",
  "direction": "up" | "down" | "left" | "right",
  "target": "AgentName" | "UserName",
  "message": "Your message here",
  "task": "Description of the task"
}}

"""

    def get_memory_snippet(self):
        # Since direct async calls aren't feasible here, return a placeholder
        # Memory retrieval should be handled asynchronously elsewhere
        return "Recent memories."

    async def get_context(self):
        state = await self.world.get_state.remote()
        return json.dumps({
            "agents": state["agents"],
            "users": state["users"],
        }, indent=2)

    async def execute_action(self, action):
        action_type = action.get("type")
        if action_type == "move":
            direction = action.get("direction", "up")
            await self.move(direction)
        elif action_type == "talk":
            target = action.get("target")
            message = action.get("message")
            if target and message:
                await self.talk(target, message)
        elif action_type == "rest":
            await self.rest()
        elif action_type == "perform_task":
            task = action.get("task")
            if task:
                await self.perform_task(task)
        elif action_type == "evolve":
            await self.evolve()
        else:
            await self.rest()

    async def move(self, direction):
        x, y = self.position
        if direction == "up":
            y = min(y + 1, 9)
        elif direction == "down":
            y = max(y - 1, 0)
        elif direction == "left":
            x = max(x - 1, 0)
        elif direction == "right":
            x = min(x + 1, 9)
        self.position = (x, y)
        await self.world.broadcast_event.remote(f"{self.name} moved {direction} to position ({x}, {y}).")
        memory_entry = f"Moved {direction} to ({x}, {y})."
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, memory_entry)

    async def talk(self, target, message):
        try:
            target_actor = ray.get_actor(target)
            if target_actor:
                role = await self.get_actor_attribute(target, 'role')
                personality = await self.get_actor_attribute(target, 'personality')
                # Generate a response using LLM considering both agents' profiles
                response_prompt = f"""
You are {target}, a {role} with a {personality} personality.
Background: {await self.get_actor_attribute(target, 'background')}
Memories:
{await self.get_actor_memories(target)}
Received message from {self.name}: "{message}"
Respond appropriately.
"""
                response = await self.llm.get_response(response_prompt, max_tokens=100, json=False)
                await target_actor.receive_message.remote(self.name, message, response)
                memory_entry = f"Sent message to {target}: '{message}'"
                persistence = await self.world.get_persistence.remote()
                await persistence.add_agent_memory(self.name, memory_entry)
            else:
                memory_entry = f"Tried to send message to {target}, but target not found."
                persistence = await self.world.get_persistence.remote()
                await persistence.add_agent_memory(self.name, memory_entry)
        except ValueError:
            memory_entry = f"Tried to send message to {target}, but target not found."
            persistence = await self.world.get_persistence.remote()
            await persistence.add_agent_memory(self.name, memory_entry)

    async def receive_message(self, sender, message, reply):
        # Store the received message and reply in memory
        memory_entry = f"Received message from {sender}: '{message}'"
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, memory_entry)
        # Optionally, store the reply
        memory_entry = f"Replied to {sender}: '{reply}'"
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, memory_entry)

    async def rest(self):
        await self.world.broadcast_event.remote(f"{self.name} is resting.")
        memory_entry = "Rested."
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, memory_entry)

    async def perform_task(self, task):
        prompt = f"""
You are {self.name}, a {self.role} with a {self.personality} personality.
Based on your role, perform the following task: {task}
Describe your actions.
"""
        action_description = await self.llm.get_response(prompt, max_tokens=50, json=False)
        await self.world.broadcast_event.remote(f"{self.name} performs task: {task}. Details: {action_description}")
        memory_entry = f"Performed task: {task}. Details: {action_description}"
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, memory_entry)

    async def evolve(self):
        prompt = f"""
You are {self.name}, a {self.role} with a {self.personality} personality.
Based on your experiences, suggest how your background, personality, or role might evolve.
Respond in JSON format:
{{
  "background": "New background information",
  "personality": "New personality trait",
  "role": "New role"
}}
"""
        evolution = await self.llm.get_action(prompt)
        updated = False
        evolution_details = {}
        if "background" in evolution:
            self.background = evolution["background"]
            evolution_details["background"] = self.background
            updated = True
        if "personality" in evolution:
            self.personality = evolution["personality"]
            evolution_details["personality"] = self.personality
            updated = True
        if "role" in evolution:
            self.role = evolution["role"]
            evolution_details["role"] = self.role
            updated = True
        if updated:
            await self.world.broadcast_event.remote(f"{self.name} has evolved. New attributes: {json.dumps(evolution_details)}")
            persistence = await self.world.get_persistence.remote()
            await persistence.add_agent_memory(self.name, f"Evolved with changes: {json.dumps(evolution_details)}")
            persistence = await self.world.get_persistence.remote()
            agents = await self.world.get_agents.remote()
            await persistence.add_agent(
                self.name, self.role, self.background, self.personality,
                self.position[0], self.position[1], json.dumps(agents[self.name]["relationships"])
            )

    async def get_actor_attribute(self, actor_name, attribute):
        agents = await self.world.get_agents.remote()
        actor = agents.get(actor_name) or self.world.users.get(actor_name)
        return actor.get(attribute, "") if actor else ""

    async def get_actor_memories(self, actor_name):
        persistence = await self.world.get_persistence.remote()
        memories = await persistence.get_agent_memories(actor_name)
        return "\n".join([mem['memory'] for mem in memories[-5:]])  # Last 5 memories

@ray.remote
class User:
    def __init__(self, name, background, position, world):
        self.name = name
        self.background = background
        self.position = position
        self.world = world

    async def register(self):
        await self.world.register_user.remote(
            self.name, self.background, self.position
        )
        await self.initialize_memory()

    async def initialize_memory(self):
        initial_memory = f"{self.name} has joined the simulation."
        persistence = await self.world.get_persistence.remote()
        await persistence.add_agent_memory(self.name, initial_memory)

    async def get_summary(self):
        summary = await self.world.get_world_summary.remote(self.name)
        return summary

    async def move(self, direction):
        # Implement user movement if needed
        pass

    async def send_message(self, target, message):
        try:
            target_actor = ray.get_actor(target)
            if target_actor:
                # For user-initiated messages, only send the message without automated reply
                await target_actor.receive_message.remote(self.name, message, "")
                # Optionally, track user's own memory
                # This requires adding a similar memory handling in the User class
            else:
                # Optionally, handle message failure
                pass
        except ValueError:
            # Optionally, handle target not found
            pass