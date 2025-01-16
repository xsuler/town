import ray
import asyncio
from actors import World, Supervisor, Agent, User, EventBoard
import os
import random
from aiohttp import web
import aiohttp_cors  # Import aiohttp_cors
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


# Startup event to initialize the World actor and other Ray actors
async def startup_event(app):
    global world
    try:
        # Initialize Ray. The `ignore_reinit_error` prevents errors if Ray is already initialized.
        ray.init(address='auto', ignore_reinit_error=True)
        print("Ray initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize Ray: {e}")
        raise

    # Initialize the World actor
    try:
        world = World.options(name="World").remote()
        print("World actor created.")
    except Exception as e:
        print(f"Failed to create World actor: {e}")
        raise

    # Initialize persistence and other components
    try:
        persistence = await world.get_persistence.remote()
        await persistence.initialize()
        print("Persistence initialized.")
    except Exception as e:
        print(f"Failed to initialize persistence: {e}")
        raise

    # Initialize Event Board
    try:
        event_board = EventBoard.remote(world)
        async def generate_events():
            await event_board.generate_events.remote()
        asyncio.create_task(generate_events())
        print("EventBoard actor created and event generation started.")
    except Exception as e:
        print(f"Failed to create EventBoard actor: {e}")
        raise

    # Initialize Supervisor
    try:
        supervisor = Supervisor.remote(world)
        async def monitor_systems():
            await supervisor.monitor_systems.remote()
        asyncio.create_task(monitor_systems())
        print("Supervisor actor created and system monitoring started.")
    except Exception as e:
        print(f"Failed to create Supervisor actor: {e}")
        raise

    # Initialize Agents
    agent_names = ["Alice", "Bob", "Charlie", "Diana"]
    roles = ["Teacher", "Shop Owner", "Doctor", "Engineer"]
    personalities = ["Friendly", "Reserved", "Aggressive", "Calm"]

    agents = []
    for name in agent_names:
        if not roles or not personalities:
            print(f"Insufficient roles or personalities to assign to agent {name}. Skipping.")
            continue  # Avoid IndexError if lists are exhausted
        role = random.choice(roles)
        roles.remove(role)
        personality = random.choice(personalities)
        personalities.remove(personality)
        position = (random.randint(0, 9), random.randint(0, 9))
        try:
            agent = Agent.options(name=name).remote(
                name=name,
                role=role,
                background=f"Background information about {name}.",
                personality=personality,
                position=position,
                world=world
            )
            agents.append(agent)
            await agent.register.remote()
            print(f"Agent '{name}' initialized and registered.")
        except Exception as e:
            print(f"Failed to initialize agent '{name}': {e}")

    # Schedule agents to decide actions periodically
    async def schedule_actions():
        while True:
            for agent in agents:
                try:
                    await agent.decide_action.remote()
                except Exception as e:
                    print(f"Error in agent deciding action: {e}")
            await asyncio.sleep(1)  # Prevent tight loop by adding a delay

    asyncio.create_task(schedule_actions())
    print("Scheduled agents to decide actions periodically.")


# Shutdown event to clean up Ray resources
async def shutdown_event(app):
    try:
        ray.shutdown()
        print("Ray has been shut down successfully.")
    except Exception as e:
        print(f"Error during Ray shutdown: {e}")


# Handler for /world_summary endpoint
async def get_world_summary(request):
    username = request.query.get("username")
    if not username:
        raise web.HTTPBadRequest(text="Username is required")

    try:
        summary = await world.get_world_summary.remote(username)
    except Exception as e:
        raise web.HTTPInternalServerError(text=f"Failed to get world summary: {e}")

    if isinstance(summary, str) and summary.startswith("Access Denied"):
        raise web.HTTPForbidden(text=summary)
    return web.json_response({"summary": summary})


# Handler for /events endpoint
async def get_events(request):
    try:
        persistence = await world.get_persistence.remote()
        events = await persistence.get_events()
    except Exception as e:
        raise web.HTTPInternalServerError(text=f"Failed to get events: {e}")
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
        raise web.HTTPBadRequest(text=f"Invalid command data: {e}")
    except Exception:
        raise web.HTTPBadRequest(text="Invalid JSON format")

    try:
        user_actor = ray.get_actor(username)
    except ValueError:
        raise web.HTTPNotFound(text="User not found")
    except Exception as e:
        raise web.HTTPInternalServerError(text=f"Error fetching user actor: {e}")

    action = command.action.lower()
    try:
        if action == "send_message":
            if not command.target or not command.message:
                raise web.HTTPBadRequest(text="Target and message are required for sending a message")
            await user_actor.send_message.remote(command.target, command.message)
            return web.json_response({"status": "Message sent"})
        elif action == "move":
            if not command.direction:
                raise web.HTTPBadRequest(text="Direction is required for moving")
            # Assuming there's a method to handle movement
            await user_actor.move.remote(command.direction)
            return web.json_response({"status": f"Moved {command.direction}"})
        else:
            raise web.HTTPBadRequest(text="Invalid action")
    except Exception as e:
        raise web.HTTPInternalServerError(text=f"Failed to execute action '{action}': {e}")


# Create the aiohttp application
app = web.Application()

# Register startup and shutdown events
app.on_startup.append(startup_event)
app.on_cleanup.append(shutdown_event)

# Add routes
app.router.add_get("/world_summary", get_world_summary)
app.router.add_get("/events", get_events)
app.router.add_post("/user_command/{username}", user_command)

# Configure default CORS settings.
# Replace "*" with specific origins for better security.
allowed_origins = [
    "*",  # Example origin
]

cors = aiohttp_cors.setup(app, defaults={
    origin: aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
    ) for origin in allowed_origins
})

# Apply CORS to all routes
for route in list(app.router.routes()):
    cors.add(route)

# Run the server
if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", 8000))
    print(f"Starting HTTP server at http://{host}:{port}")
    web.run_app(app, host=host, port=port)
