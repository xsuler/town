import sys
from game import GameClient

def main():
    if len(sys.argv) != 3:
        print("Usage: python main.py <Username> <Server_URL>")
        sys.exit(1)
    username = sys.argv[1]
    server_url = sys.argv[2]

    client = GameClient(username, server_url)
    client.run()

if __name__ == "__main__":
    main()