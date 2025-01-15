import ray
import asyncio
from actors import World, Supervisor, Agent, User, EventBoard
import os
import random
from aiohttp import web
from pydantic import BaseModel, ValidationError


# Define the Pydantic model for user commands
class UserCommand(BaseModel):
    action: str
    target: str = None
    direction: str = None
    message: str = None
    task: str = None


# Global variable to hold the World actor
world = None


# Startup event to initialize the World actor
async def startup_event():
    global world
    ray.init(address='auto')
    world = World.options(name="World").remote()
    p = await world.get_persistence.remote()
    await p.initialize()

    # Initialize Event Board
    event_board = EventBoard.remote(world)
    async def run1():
        await event_board.generate_events.remote()

    asyncio.create_task(run1())

    # Initialize Supervisor
    supervisor = Supervisor.remote(world)
    async def run2():
        await supervisor.monitor_systems.remote()
    asyncio.create_task(run2())

    # Initialize Agents
    agent_names = ["Alice", "Bob", "Charlie", "Diana"]
    roles = ["Teacher", "Shop Owner", "Doctor", "Engineer"]
    personalities = ["Friendly", "Reserved", "Aggressive", "Calm"]

    agents = []
    for name in agent_names:
        role = random.choice(roles)
        roles.remove(role)
        personality = random.choice(personalities)
        personalities.remove(personality)
        position = (random.randint(0, 9), random.randint(0, 9))
        agents.append(
            Agent.options(name=name).remote(name, role, f"Background information about {name}.", personality, position,
                                            world))

        await agents[-1].register.remote()

    # Initialize Users
    # Schedule agents to decide actions periodically
    async def schedule_actions():
        while True:
            for agent in agents:
                await agent.decide_action.remote()
            await asyncio.sleep(random.randint(1, 3))  # Random interval between actions

    asyncio.create_task(schedule_actions())


# Handler for /world_summary endpoint
async def get_world_summary(request):
    username = request.query.get("username")
    if not username:
        raise web.HTTPBadRequest(text="Username is required")

    summary = await world.get_world_summary.remote(username)
    if summary.startswith("Access Denied"):
        raise web.HTTPForbidden(text=summary)
    return web.json_response({"summary": summary})


# Handler for /events endpoint
async def get_events(request):
    persistence = await world.get_persistence.remote()
    events = await persistence.get_events()
    return web.json_response({"events": events})


# Handler for /user_command/{username} endpoint
async def user_command(request):
    username = request.match_info.get("username")
    if not username:
        raise web.HTTPBadRequest(text="Username is required")

    try:
        data = await request.json()
        command = UserCommand(**data)
    except ValidationError as e:
        raise web.HTTPBadRequest(text=str(e))

    try:
        user_actor = ray.get_actor(username)
    except ValueError:
        raise web.HTTPNotFound(text="User not found")

    action = command.action.lower()
    if action == "send_message":
        if not command.target or not command.message:
            raise web.HTTPBadRequest(text="Target and message are required for sending a message")
        try:
            await user_actor.send_message.remote(command.target, command.message)
            return web.json_response({"status": "Message sent"})
        except ValueError:
            raise web.HTTPNotFound(text="Target user/agent not found")
    elif action == "move":
        if not command.direction:
            raise web.HTTPBadRequest(text="Direction is required for moving")
        # Implement user movement if necessary
        return web.json_response({"status": f"Moved {command.direction}"})
    else:
        raise web.HTTPBadRequest(text="Invalid action")



# Create the aiohttp application
app = web.Application()

# Add startup event

# Add routes
app.router.add_get("/world_summary", get_world_summary)
app.router.add_get("/events", get_events)
app.router.add_post("/user_command/{username}", user_command)

# Run the server
if __name__ == "__main__":
    asyncio.run(startup_event())
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 8000))
    print(f"Starting HTTP server at http://{host}:{port}")
    web.run_app(app, host=host, port=port)