import pytest
from fastapi.testclient import TestClient
from chat.chatroom_server import app, storage

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Reset storage before each test
    storage.rooms.clear()
    storage.messages.clear()
    storage.users.clear()
    storage.room_users.clear()
    yield
    # No teardown actions required

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_create_user():
    response = client.post("/users/", json={"name": "Alice", "description": "A user"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alice"
    assert data["description"] == "A user"
    assert "id" in data

def test_create_user_with_no_description_and_spaces():
    response = client.post("/users/", json={"name": "Cheshire Cat"})
    print(response.json())
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Cheshire Cat"
    assert data["description"] == ""
    assert "id" in data

def test_create_duplicate_user_fails():
    client.post("/users/", json={"name": "Dude"})
    response = client.post("/users/", json={"name": "Dude", "description": ""})
    assert response.status_code == 409

def test_create_duplicate_user_with_differnt_description_fails():
    client.post("/users/", json={"name": "Dude", "description": "The Dude"})
    response = client.post("/users/", json={"name": "Dude", "description": "El Duderino"})
    assert response.status_code == 409

def test_get_user_success():
    user = client.post("/users/", json={"name": "Elliot", "description": "a.k.a Sam Sepiol"}).json()
    uid = user["id"]
    response = client.get(f"/users/{uid}")
    assert response.status_code == 200
    assert response.json()["name"] == "Elliot"

def test_get_user_not_found():
    response = client.get("/users/some_uuid_here")
    assert response.status_code == 404

def test_get_users_list():
    client.post("/users/", json={"name": "Romero", "description": "DJ Mobley"})
    client.post("/users/", json={"name": "Trenton", "description": ""})
    response = client.get("/users/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

def test_create_empty_room_fails():
    response = client.post("/rooms/", json={"name": ""})
    assert response.status_code == 400

def test_create_room_success():
    response = client.post("/rooms/", json={"name": "AllSafe"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "AllSafe"
    assert "id" in data

def test_create_duplicate_room_fails():
    client.post("/rooms/", json={"name": "E-Corp"})
    response = client.post("/rooms/", json={"name": "E-Corp"})
    assert response.status_code == 400

def test_get_room_success():
    room = client.post("/rooms/", json={"name": "Rons Coffee"}).json()
    rid = room["id"]
    response = client.get(f"/rooms/{rid}")
    assert response.status_code == 200
    assert response.json()["name"] == "Rons Coffee"

def test_get_room_not_found():
    response = client.get("/rooms/some_uuid_here")
    assert response.status_code == 404

def test_get_rooms_list():
    client.post("/rooms/", json={"name": "Red Wheelbarrow BBQ"})
    client.post("/rooms/", json={"name": "Fun Society"})
    response = client.get("/rooms/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

def test_add_and_get_messages():
    user = client.post("/users/", json={"name": "Whiterose"}).json()
    room = client.post("/rooms/", json={"name": "Deus Group"}).json()
    # Simulate sending messages directly via storage
    m1 = storage.add_message(room_id=room["id"], user_id=user["id"], user_name=user["name"], content="Hello")
    m2 = storage.add_message(room_id=room["id"], user_id=user["id"], user_name=user["name"], content="World")
    response = client.get(f"/messages/{room['id']}?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[-1]["content"] == "World"

def test_get_messages_room_not_found():
    response = client.get("/messages/some_uuid_here")
    assert response.status_code == 404

def test_room_users_join_and_leave():
    # Simulate joining/leaving via storage
    user1 = storage.create_user("Darlene")
    user2 = storage.create_user("Dom")
    room = storage.create_room("The Bar")
    storage.add_user_to_room(room.id, user1.id)
    storage.add_user_to_room(room.id, user2.id)
    users = storage.get_room_users(room.id)
    assert len(users) == 2
    storage.remove_user_from_room(room.id, user1.id)
    users = storage.get_room_users(room.id)
    assert len(users) == 1
    assert users[0].id == user2.id

def test_remove_user_full_cleanup():
    user = storage.create_user("Goldfish")
    room = storage.create_room("Fishbowl")
    storage.add_user_to_room(room.id, user.id)
    assert user.id in storage.room_users[room.id]
    storage.remove_user(user.id)
    assert user.id not in storage.users
    assert user.id not in storage.room_users[room.id]

def test_add_message_room_not_found():
    user = storage.create_user("Joanna")
    with pytest.raises(ValueError):
        storage.add_message(room_id="doesnotexist", user_id=user.id, user_name=user.name, content="msg")

def test_add_user_to_room_not_found():
    user = storage.create_user("Shayla")
    with pytest.raises(ValueError):
        storage.add_user_to_room(room_id="doesnotexist", user_id=user.id)

def test_add_user_to_room_user_not_found():
    room = storage.create_room("Washington Township Plant")
    with pytest.raises(ValueError):
        storage.add_user_to_room(room_id=room.id, user_id="doesnotexist")

def test_remove_user_from_room_not_in_room():
    user = storage.create_user("Gideon")
    room = storage.create_room("Gideon's Loft")
    # Not in room yet
    with pytest.raises(ValueError):
        storage.remove_user_from_room(room_id=room.id, user_id=user.id)
