#!/usr/bin/env python3

import asyncio
import socketio
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime


class ChatroomClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.http_url = server_url
        self.user: Optional[Dict[str, Any]] = None
        self.current_room: Optional[Dict[str, Any]] = None
        self.sio = socketio.AsyncClient()
        self.running = True

        # Set up socket event handlers
        self.setup_socket_handlers()

    def setup_socket_handlers(self):
        @self.sio.event
        async def connect():
            print("\n✅ Connected to chatroom server!")

        @self.sio.event
        async def disconnect():
            print("\n❌ Disconnected from server")

        @self.sio.event
        async def room_joined(data):
            print(f"\n✅ Successfully joined room: {data.get('room_id')}")
            self.print_prompt()

        @self.sio.event
        async def message(data):
            if self.current_room and data.get("room_id") == self.current_room["id"]:
                timestamp = datetime.fromtimestamp(data["created_at"]).strftime(
                    "%H:%M:%S"
                )
                print(f"\n[{timestamp}] {data['user_name']}: {data['content']}")
                self.print_prompt()

        @self.sio.event
        async def user_joined(data):
            if self.current_room and data.get("room_id") == self.current_room["id"]:
                # Don't show notification for ourselves
                if data.get("user_id") != self.user["id"]:
                    print(f"\n👋 {data['user_name']} joined the room")
                    self.print_prompt()

        @self.sio.event
        async def user_left(data):
            if self.current_room and data.get("room_id") == self.current_room["id"]:
                print(f"\n👋 {data['user_name']} left the room")
                self.print_prompt()

        @self.sio.event
        async def error(data):
            print(f"\n❌ Error: {data.get('message', 'Unknown error')}")
            self.print_prompt()

    def print_prompt(self):
        room_indicator = f" [{self.current_room['name']}]" if self.current_room else ""
        user_name = self.user["name"] if self.user else "Unknown"
        print(f"{user_name}{room_indicator}> ", end="", flush=True)

    async def create_user(self, name: str, description: str = "") -> bool:
        """Create a new user"""
        try:
            response = requests.post(
                f"{self.http_url}/users/",
                json={"name": name, "description": description},
            )
            if response.status_code == 201:
                self.user = response.json()
                print(f"✅ User '{name}' created successfully!")
                return True
            else:
                print(
                    f"❌ Failed to create user: {response.json().get('detail', 'Unknown error')}"
                )
                return False
        except ValueError as e:
            print(f"🙅‍♂️ {e}")
            return False
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False

    def get_rooms(self) -> List[Dict[str, Any]]:
        """Get list of all rooms"""
        try:
            response = requests.get(f"{self.http_url}/rooms/")
            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"❌ Failed to get rooms: {response.json().get('detail', 'Unknown error')}"
                )
                return []
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            return []

    def get_users(self) -> List[Dict[str, Any]]:
        """Get list of all users"""
        try:
            response = requests.get(f"{self.http_url}/users/")
            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"❌ Failed to get users: {response.json().get('detail', 'Unknown error')}"
                )
                return []
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            return []

    def create_room(self, name: str) -> bool:
        """Create a new room"""
        try:
            response = requests.post(
                f"{self.http_url}/rooms/",
                json={"name": name},
            )
            if response.status_code == 201:
                print(f"✅ Room '{name}' created successfully!")
                return True
            else:
                print(
                    f"❌ Failed to create room: {response.json().get('detail', 'Unknown error')}"
                )
                return False
        except requests.RequestException as e:
            print(f"❌ Connection error: {e}")
            return False

    async def join_room(self, room_name: str) -> bool:
        """Join a room by name"""
        rooms = self.get_rooms()
        room = next((r for r in rooms if r["name"].lower() == room_name.lower()), None)

        if not room:
            print(f"❌ Room '{room_name}' not found")
            return False

        try:
            # Leave current room if in one
            if self.current_room:
                await self.leave_current_room()

            # Join the new room
            await self.sio.emit(
                "join",
                {
                    "room_id": room["id"],
                    "user_id": self.user["id"],
                    "user_name": self.user["name"],
                },
            )

            # Wait a moment for the server to process the join
            await asyncio.sleep(0.1)

            self.current_room = room
            print(f"✅ Joined room '{room_name}'")
            return True
        except Exception as e:
            print(f"❌ Failed to join room: {e}")
            return False

    async def leave_current_room(self):
        """Leave the current room"""
        if not self.current_room:
            print("❌ You're not in any room")
            return

        try:
            await self.sio.emit(
                "leave_room",
                {"room_id": self.current_room["id"], "user_id": self.user["id"]},
            )

            room_name = self.current_room["name"]
            self.current_room = None
            print(f"✅ Left room '{room_name}'")
        except Exception as e:
            print(f"❌ Failed to leave room: {e}")

    async def send_message(self, content: str):
        """Send a message to the current room"""
        if not self.current_room:
            print("❌ You need to join a room first")
            return

        try:
            await self.sio.emit(
                "send_message",
                {
                    "room_id": self.current_room["id"],
                    "user_id": self.user["id"],
                    "content": content,
                },
            )
        except Exception as e:
            print(f"❌ Failed to send message: {e}")

    def print_help(self):
        """Print available commands"""
        print("\n📋 Available Commands:")
        print("  /help                  - Show this help message")
        print("  /rooms                 - List all rooms")
        print("  /users                 - List all users")
        print("  /create <room_name>    - Create a new room")
        print("  /join <room_name>      - Join a room by name")
        print("  /join                  - Show room list and join interactively")
        print("  /leave                 - Leave current room")
        print("  /quit                  - Exit the application")
        print("  <message>              - Send a message to current room")
        print()

    async def handle_join_interactive(self):
        """Interactive room joining"""
        rooms = self.get_rooms()
        if not rooms:
            print("❌ No rooms available")
            return

        print("\n📋 Available Rooms:")
        for i, room in enumerate(rooms, 1):
            created_at = datetime.fromtimestamp(room["created_at"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            print(f"  {i}. {room['name']} (created: {created_at})")

        try:
            choice = input("\nEnter room number or name: ").strip()

            # Try parsing as number first
            try:
                room_index = int(choice) - 1
                if 0 <= room_index < len(rooms):
                    await self.join_room(rooms[room_index]["name"])
                    return
            except ValueError:
                pass

            # Try as room name
            await self.join_room(choice)
        except KeyboardInterrupt:
            print("\n❌ Cancelled")

    async def process_command(self, command: str):
        """Process a user command"""
        command = command.strip()

        if command == "/help":
            self.print_help()
        elif command == "/rooms":
            rooms = self.get_rooms()
            if rooms:
                print("\n📋 Available Rooms:")
                for room in rooms:
                    created_at = datetime.fromtimestamp(room["created_at"]).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    print(f"  • {room['name']} (created: {created_at})")
            else:
                print("📋 No rooms available")
        elif command == "/users":
            users = self.get_users()
            if users:
                print("\n👥 Users:")
                for user in users:
                    status = " (you)" if user["id"] == self.user["id"] else ""
                    print(f"  • {user['name']}{status}")
                    if user.get("description"):
                        print(f"    {user['description']}")
            else:
                print("👥 No users found")
        elif command.startswith("/create "):
            room_name = command[8:].strip()
            if room_name:
                self.create_room(room_name)
            else:
                print("❌ Please provide a room name")
        elif command.startswith("/join "):
            room_name = command[6:].strip()
            if room_name:
                await self.join_room(room_name)
            else:
                print("❌ Please provide a room name")
        elif command == "/join":
            await self.handle_join_interactive()
        elif command == "/leave":
            await self.leave_current_room()
        elif command == "/quit":
            self.running = False
            print("👋 Goodbye!")
        elif command.startswith("/"):
            print("❌ Unknown command. Type /help for available commands.")
        else:
            # Regular message
            if command:
                await self.send_message(command)

    async def input_loop(self):
        """Handle user input in a separate thread"""
        loop = asyncio.get_event_loop()

        while self.running:
            try:
                self.print_prompt()
                # Use run_in_executor to make input non-blocking
                user_input = await loop.run_in_executor(None, input)
                if user_input:
                    await self.process_command(user_input)
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                self.running = False
                break
            except EOFError:
                self.running = False
                break

    async def run(self):
        """Main application loop"""
        print("🚀 Welcome to the Chatroom Client!")
        print(f"🔗 Connecting to {self.server_url}")

        # Get user details
        while True:
            try:
                name = input("Enter your name: ").strip()
                if name:
                    description = input("Enter a description (optional): ").strip()
                    if await self.create_user(name, description):
                        break
                else:
                    print("❌ Name cannot be empty")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                return

        # Connect to server
        try:
            await self.sio.connect(self.server_url)
        except Exception as e:
            print(f"❌ Failed to connect to server: {e}")
            return

        # Show help
        self.print_help()

        # Start input loop
        try:
            await self.input_loop()
        finally:
            if self.sio.connected:
                await self.sio.disconnect()


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Chatroom Client")
    parser.add_argument(
        "--server",
        default="http://localhost:8000",
        help="Server URL (default: http://localhost:8000)",
    )

    args = parser.parse_args()

    client = ChatroomClient(args.server)
    await client.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
