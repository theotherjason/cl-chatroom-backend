import logging
import os
import socketio
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from time import time
from typing import Dict, List, Optional, Set


# set up logging
environment = os.getenv("APP_ENV", "local")
if environment == "production":
    log_level = logging.INFO
else:
    log_level = logging.DEBUG

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
logger.info(f"logger set up using log level {log_level}")


# main models ------------------------------------------------------
# each message contains user_id and user_name for simplicity even
# though the name could change (not currently implemented)
class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    room_id: str
    user_id: str
    user_name: str
    content: str
    created_at: float = Field(default_factory=lambda: time())

    def __str__(self):
        return (
            f"Message(id={self.id}, room_id={self.room_id}, user_id={self.user_id}, "
            f"user_name={self.user_name}, content={self.content}, created_at={self.created_at})"
        )


class Chatroom(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    created_at: float = Field(default_factory=lambda: time())

    def __str__(self):
        return f"Chatroom(id={self.id}, name={self.name}, created_at={self.created_at})"


class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str

    def __str__(self):
        return f"User(id={self.id}, name={self.name}, description={self.description})"


# request models ---------------------------------------------------
class CreateUserRequest(BaseModel):
    name: str
    description: Optional[str] = ""


class CreateRoomRequest(BaseModel):
    name: str


class CreateMessageRequest(BaseModel):
    content: str
    user_id: str
    user_name: str
    room_id: str


class JoinRoomRequest(BaseModel):
    user_id: str
    user_name: str
    room_id: str


class LeaveRoomRequest(BaseModel):
    user_id: str
    room_id: str


# main storage class -----------------------------------------------
class ChatStorage:
    def __init__(self):
        self.rooms: Dict[str, Chatroom] = {}
        self.messages: Dict[str, List[Message]] = {}
        self.users: Dict[str, User] = {}
        self.room_users: Dict[str, Set[str]] = {}

    def create_user(self, name: str, description: str = "") -> User:
        if any(u.name.lower() == name.lower() for u in self.users.values()):
            raise ValueError(f"User with name {name} already exists")
        user = User(name=name, description=description)
        logger.info(f"created user {user}")
        self.users[user.id] = user
        return user

    def get_user(self, user_id: str) -> User:
        if user_id not in self.users:
            raise ValueError(f"User with id {user_id} does not exist")
        return self.users[user_id]

    def get_users(self) -> List[User]:
        logger.debug(f"{[user for user in self.users.values()]}")
        return list(self.users.values())

    def create_room(self, name: str) -> Chatroom:
        if not name.strip():
            raise ValueError("Room name can't be empty")
        if any(u.name.lower() == name.lower() for u in self.rooms.values()):
            raise ValueError(f"Room with name {name} already exists")
        room = Chatroom(name=name)
        self.rooms[room.id] = room
        self.messages[room.id] = []
        self.room_users[room.id] = set()
        logger.info(f"created room {room}")
        return room

    def get_room(self, room_id: str) -> Chatroom:
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        room = self.rooms.get(room_id)
        logger.debug(f"getting room {room}")
        return room

    def get_rooms(self) -> List[Chatroom]:
        rooms = self.rooms.values()
        logger.debug(f"getting rooms: {[room for room in rooms]}")
        return list(rooms)

    def add_user_to_room(self, room_id: str, user_id: str) -> None:
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        if user_id not in self.users:
            raise ValueError(f"User with id {user_id} does not exist")
        logger.debug(f"adding {self.users[user_id]} to {self.rooms[room_id]}")
        self.room_users[room_id].add(user_id)

    def remove_user_from_room(self, room_id: str, user_id: str) -> None:
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        if user_id not in self.users:
            raise ValueError(f"User with id {user_id} does not exist")
        if user_id not in self.room_users[room_id]:
            raise ValueError(f"User with id {user_id} is not in room with id {room_id}")
        logger.debug(f"removing {self.users[user_id]} from {self.rooms[room_id]}")
        self.room_users[room_id].remove(user_id)

    def get_room_users(self, room_id: str) -> List[User]:
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        users = [self.users[user_id] for user_id in self.room_users[room_id]]
        logger.debug(f"getting users in room {self.rooms[room_id]}:  {users}")
        return users

    def add_message(
        self, room_id: str, user_id: str, user_name: str, content: str
    ) -> Message:
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        message = Message(
            room_id=room_id, user_id=user_id, user_name=user_name, content=content
        )
        self.messages[room_id].append(message)
        logger.debug(f"added message: {message}")
        return message

    def get_messages(self, room_id: str, limit: int = 50) -> List[Message]:
        """Get messages for a room with optional limit"""
        if room_id not in self.rooms:
            raise ValueError(f"Room with id {room_id} does not exist")
        messages = self.messages.get(room_id, [])
        logger.debug(f"got a list of message from {self.rooms[room_id]}")
        return messages[-limit:] if limit > 0 else messages

    def remove_user(self, user_id: str):
        # Remove user from all rooms
        for room_id, users_set in self.room_users.items():
            if user_id in users_set:
                users_set.remove(user_id)
        user = self.users[user_id]
        logger.debug(f"removed {user} from all rooms")
        if user_id in self.users:
            del self.users[user_id]
        logger.debug(f"removed {user} completely")


# initialize storage
storage = ChatStorage()
sid_user_map: Dict[str, str] = {}

# set up FastAPI and Socket.IO
app = FastAPI(
    title="Chatroom Backend",
    description="A backend for a chatroom application",
    version="0.0.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# set up Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=False,
)

# create ASGI app
socket_app = socketio.ASGIApp(sio, app)


# set up routes
@app.get("/")
async def health_check():
    return {"status": "healthy", "service": "chatroom-server"}


@app.post("/users/", status_code=201, tags=["Users"])
async def create_user(request: CreateUserRequest):
    try:
        user = storage.create_user(name=request.name, description=request.description)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return user


@app.get("/users/{user_id}", tags=["Users"])
async def get_user(user_id: str):
    try:
        user = storage.get_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return user


@app.get("/users/", tags=["Users"])
async def get_users():
    return storage.get_users()


@app.post("/rooms/", status_code=201, tags=["Rooms"])
async def create_room(request: CreateRoomRequest):
    try:
        room = storage.create_room(name=request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return room


@app.get("/rooms/{room_id}", tags=["Rooms"])
async def get_room(room_id: str):
    try:
        room = storage.get_room(room_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return room


@app.get("/rooms/", tags=["Rooms"])
async def get_rooms():
    return storage.get_rooms()


@app.get("/messages/{room_id}", tags=["Messages"])
async def get_room_messages(room_id: str, limit: int = 50):
    try:
        messages = storage.get_messages(room_id=room_id, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return messages


@sio.event
async def connect(sid, _environ):
    logger.info(f"Client connected: {sid}")
    await sio.emit("connect_response", {"status": "connected"}, room=sid)


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")
    user_id = sid_user_map.get(sid)
    if user_id:
        # Remove user from all rooms and notify others
        for room_id, users_set in list(storage.room_users.items()):
            if user_id in users_set:
                try:
                    storage.remove_user_from_room(room_id, user_id)
                    await sio.emit(
                        "user_left",
                        {
                            "status": "left",
                            "room_id": room_id,
                            "user_id": user_id,
                            "user_name": storage.get_user(user_id).name
                            if user_id in storage.users
                            else "unknown",
                        },
                        room=room_id,
                    )
                except Exception as e:
                    logger.error(f"Error removing user from room on disconnect: {e}")
        # Remove user from storage
        try:
            storage.remove_user(user_id)
            logger.info(f"User {user_id} removed from storage on disconnect")
        except Exception as e:
            logger.error(f"Error removing user from storage: {e}")
        # Remove sid mapping
        del sid_user_map[sid]


@sio.event
async def join(sid, data):
    try:
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        user_name = data.get("user_name")

        if not all([room_id, user_id, user_name]):
            await sio.emit("error", {"message": "Missing required fields"}, room=sid)
            return

        # add user to room
        try:
            storage.add_user_to_room(room_id=room_id, user_id=user_id)
        except ValueError as e:
            await sio.emit("error", {"message": str(e)}, room=sid)
            return

        # join room
        await sio.enter_room(sid, room_id)

        # track sid to user_id mapping
        sid_user_map[sid] = user_id

        # notify user
        await sio.emit(
            "room_joined",
            {
                "status": "joined",
                "room_id": room_id,
                "user_id": user_id,
                "user_name": user_name,
            },
            room=sid,
        )

        # notify other users in the room
        await sio.emit(
            "user_joined",
            {
                "status": "joined",
                "room_id": room_id,
                "user_id": user_id,
                "user_name": user_name,
            },
            room=room_id,
        )

        logger.info(f"User {user_name} ({user_id}) has joined room {room_id}")

    except Exception as e:
        logger.error(f"Error in join: {str(e)}")
        await sio.emit("error", {"message": "Server error"}, room=sid)


@sio.event
async def leave_room(sid, data):
    try:
        room_id = data.get("room_id")
        user_id = data.get("user_id")

        if not all([room_id, user_id]):
            await sio.emit("error", {"message": "Missing required fields"}, room=sid)
            return

        # remove user from room
        try:
            storage.remove_user_from_room(room_id=room_id, user_id=user_id)
        except ValueError as e:
            await sio.emit("error", {"message": str(e)}, room=sid)
            return

        # leave room
        await sio.leave_room(sid, room_id)

        # notify all users in the room, not just the leaver
        await sio.emit(
            "user_left",
            {
                "status": "left",
                "room_id": room_id,
                "user_id": user_id,
                "user_name": storage.get_user(user_id).name
                if user_id in storage.users
                else "unknown",
            },
            room=room_id,
        )

        logger.info(f"User {user_id} left room {room_id}")

    except Exception as e:
        logger.error(f"Error in leave_room: {str(e)}")


@sio.event
async def send_message(sid, data):
    try:
        room_id = data.get("room_id")
        user_id = data.get("user_id")
        content = data.get("content")

        if not all([room_id, user_id, content]):
            await sio.emit("error", {"message": "Missing required fields"}, room=sid)
            return

        if not content.strip():
            await sio.emit("error", {"message": "Message cannot be empty"}, room=sid)
            return

        # get user
        try:
            user = storage.get_user(user_id)
        except ValueError as e:
            await sio.emit("error", {"message": str(e)}, room=sid)
            return

        try:
            message = storage.add_message(
                room_id=room_id, user_id=user.id, user_name=user.name, content=content
            )
        except ValueError as e:
            await sio.emit("error", {"message": str(e)}, room=sid)
            return

        await sio.emit(
            "message",
            {
                "id": message.id,
                "room_id": message.room_id,
                "user_id": message.user_id,
                "user_name": message.user_name,
                "content": message.content,
                "created_at": message.created_at,
            },
            room=room_id,
        )

    except Exception as e:
        logger.error(f"Error in send_message: {str(e)}")
        await sio.emit("error", {"message": "Server error"}, room=sid)


@sio.event
async def receive_message(sid, data):
    try:
        room_id = data.get("room_id")
        if not room_id:
            await sio.emit(
                "error", {"message": "Missing room_id for receive_message"}, room=sid
            )
            return
        await sio.enter_room(sid, room_id)
        await sio.emit(
            "info", {"message": f"Subscribed to messages in room {room_id}"}, room=sid
        )
    except Exception as e:
        logger.error(f"Error in receive_message: {str(e)}")
        await sio.emit(
            "error", {"message": "Server error in receive_message"}, room=sid
        )


# Use the socket_app as the ASGI application
# Run with: uvicorn chat.chatroom_server:socket_app --host 0.0.0.0 --port 8000
