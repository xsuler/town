import pygame
import requests
import random
import threading
import time
import sys

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
GRID_SIZE = 10
CELL_SIZE = 50
FPS = 30

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (200, 0, 0)
GREEN = (0, 200, 0)
BLUE = (0, 0, 200)
GRAY = (200, 200, 200)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
ORANGE = (255, 165, 0)

class GameClient:
    def __init__(self, username, server_url):
        pygame.init()
        self.username = username
        self.server_url = server_url
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(f"Simulation Client - {self.username}")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 24)

        # Game state
        self.world_summary = ""
        self.events = []
        self.agents = {}
        self.users = {}

        # Colors for agents and users
        self.agent_colors = {}
        self.user_color = ORANGE
        self.background_color = GRAY

        # Start data fetching thread
        self.running = True
        threading.Thread(target=self.fetch_data_loop, daemon=True).start()

    def fetch_data_loop(self):
        while self.running:
            self.fetch_data()
            time.sleep(1)  # Refresh every 60 seconds

    def fetch_data(self):
        try:
            # Fetch world summary
            summary_resp = requests.get(f"{self.server_url}/world_summary", params={"username": self.username})
            if summary_resp.status_code == 200:
                self.world_summary = summary_resp.json().get("summary", "")
            else:
                self.world_summary = summary_resp.json().get("detail", "Unable to fetch summary.")

            # Fetch events
            events_resp = requests.get(f"{self.server_url}/events")
            print(events_resp.text)
            if events_resp.status_code == 200:
                self.events = events_resp.json().get("events", [])
                print(self.events)
            else:
                self.events = []

            # Optional: Fetch agents and users positions if API provides
            # For now, we'll simulate positions based on events
            # This can be extended with proper APIs

        except Exception as e:
            print(f"Failed to fetch data: {e}")

    def draw_grid(self):
        for x in range(0, GRID_SIZE * CELL_SIZE, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (x, 0), (x, GRID_SIZE * CELL_SIZE))
        for y in range(0, GRID_SIZE * CELL_SIZE, CELL_SIZE):
            pygame.draw.line(self.screen, WHITE, (0, y), (GRID_SIZE * CELL_SIZE, y))

    def draw_agents_and_users(self):
        # For simplicity, parse events to determine positions
        # This is a placeholder. Ideally, fetch positions from an API.
        for event in self.events[-50:]:  # Limit to last 50 events to reduce processing
            description = event['description']
            if "moved" in description:
                parts = description.split()
                try:
                    name = parts[0]
                    direction = parts[2]
                    pos_part = parts[-1].strip("().")
                    x, y = map(int, pos_part.split(","))
                    if name not in self.agents and name not in self.users:
                        # Determine if it's an agent or user
                        color = BLUE if name.startswith("A") else GREEN  # Simple heuristic
                        self.agent_colors[name] = color
                        self.agents[name] = (x, y)
                except:
                    continue
            elif "has joined the simulation" in description:
                name = description.split()[0]
                if name.startswith("User"):
                    color = self.user_color
                    self.users[name] = (random.randint(0, 9), random.randint(0, 9))
                else:
                    color = BLUE
                    self.agent_colors[name] = color

        # Draw agents
        for name, pos in self.agents.items():
            color = self.agent_colors.get(name, BLUE)
            pygame.draw.circle(self.screen, color, (pos[0] * CELL_SIZE + CELL_SIZE//2, pos[1] * CELL_SIZE + CELL_SIZE//2), CELL_SIZE//2 - 5)
            # Render agent name
            text = self.font.render(name, True, BLACK)
            self.screen.blit(text, (pos[0] * CELL_SIZE + 5, pos[1] * CELL_SIZE + 5))

        # Draw users
        for name, pos in self.users.items():
            pygame.draw.rect(self.screen, self.user_color, (pos[0] * CELL_SIZE + 5, pos[1] * CELL_SIZE + 5, CELL_SIZE - 10, CELL_SIZE - 10))
            # Render user name
            text = self.font.render(name, True, BLACK)
            self.screen.blit(text, (pos[0] * CELL_SIZE + 5, pos[1] * CELL_SIZE + 5))

    def render_text(self, text, pos, color=BLACK):
        img = self.font.render(text, True, color)
        self.screen.blit(img, pos)

    def send_command(self, data):
        try:
            response = requests.post(f"{self.server_url}/user_command/{self.username}", json=data)
            if response.status_code == 200:
                print(response.json().get("status", "Command executed successfully."))
            else:
                print(response.json().get("detail", "Failed to execute command."))
        except Exception as e:
            print(f"Failed to send command: {e}")

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_m:
                        # Example: Send a message
                        threading.Thread(target=self.send_message_prompt, daemon=True).start()
                    elif event.key in [pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT]:
                        direction = {pygame.K_UP: "up", pygame.K_DOWN: "down",
                                     pygame.K_LEFT: "left", pygame.K_RIGHT: "right"}[event.key]
                        data = {"action": "move", "direction": direction}
                        threading.Thread(target=self.send_command, args=(data,), daemon=True).start()

            self.screen.fill(self.background_color)
            self.draw_grid()
            self.draw_agents_and_users()

            # Display World Summary
            self.render_text("World Summary:", (10, GRID_SIZE * CELL_SIZE + 10))
            summary_lines = self.world_summary.split('\n')
            for idx, line in enumerate(summary_lines[:3]):  # Show only first 3 lines
                self.render_text(line, (10, GRID_SIZE * CELL_SIZE + 30 + idx * 20))

            # Display Events
            self.render_text("Events:", (400, GRID_SIZE * CELL_SIZE + 10))
            for idx, event in enumerate(self.events[-5:]):  # Show last 5 events
                event_text = f"[{event['timestamp']}] {event['description']}"
                self.render_text(event_text, (400, GRID_SIZE * CELL_SIZE + 30 + idx * 20))

            pygame.display.flip()
            self.clock.tick(FPS)

    def send_message_prompt(self):
        # Simple console prompt for sending a message
        target = input("Enter target Agent/User name: ")
        message = input("Enter your message: ")
        if target and message:
            data = {"action": "send_message", "target": target, "message": message}
            self.send_command(data)
        else:
            print("Target and message cannot be empty.")