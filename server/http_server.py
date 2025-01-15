from aiohttp import web
from pydantic import BaseModel, ValidationError
import ray
import asyncio
from actors import World


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
async def startup_event(app):
    global world
    try:
        world = ray.get_actor("World")
    except ValueError:
        world = await World.options(name="World").remote()


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
    persistence = await world.persistence.remote()
    events = await persistence.get_events.remote()
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


# Handler for /economy endpoint
async def get_economy(request):
    economy = await world.get_economy.remote()
    return web.json_response({"economy": economy})


# Handler for /weather endpoint
async def get_weather(request):
    weather = await world.get_weather.remote()
    return web.json_response({"weather": weather})


# Create the aiohttp application
app = web.Application()

# Add startup event
app.on_startup.append(startup_event)

# Add routes
app.router.add_get("/world_summary", get_world_summary)
app.router.add_get("/events", get_events)
app.router.add_post("/user_command/{username}", user_command)
app.router.add_get("/economy", get_economy)
app.router.add_get("/weather", get_weather)

# Run the server
if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8000)