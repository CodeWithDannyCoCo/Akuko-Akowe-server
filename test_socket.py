#!python
import socketio
import asyncio
import json
import django
import os
import base64

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog_api.settings')
django.setup()

from communications.models import ChatRoom
from django.contrib.auth import get_user_model

User = get_user_model()

# Create a Socket.io client
sio = socketio.AsyncClient()

@sio.event
async def connect():
    print("✓ Connected to Socket.io server!")
    
    try:
        # Get the user from the token
        token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzM4MDAzNjgxLCJpYXQiOjE3MzgwMDAwODEsImp0aSI6IjE4OWNiOWU0MGMwZjRhMzc5MGRlYTk2NzQ4Y2M4MDBhIiwidXNlcl9pZCI6NH0.3RcB-ZOgj9mj4DAFCLmIN_iJZHNu-7Vwo8K5KQT2Djs'
        import jwt
        from django.conf import settings
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        print(f"✓ Token decoded, user_id: {payload['user_id']}")
        user = await User.objects.aget(id=payload['user_id'])
        print(f"✓ User retrieved: {user.email}")
        
        # Try to get an existing test room first
        room = await ChatRoom.objects.filter(name="Test Room").afirst()
        
        if room:
            print(f"✓ Found existing test room (ID: {room.id})")
        else:
            room = await ChatRoom.objects.acreate(name="Test Room")
            print(f"✓ Created new test room (ID: {room.id})")
        
        # Make sure user is a participant
        if not await room.participants.filter(id=user.id).aexists():
            await room.participants.aadd(user)
            print(f"✓ Added user {user.email} to room {room.id}")
        else:
            print(f"✓ User {user.email} already in room {room.id}")
        
        print(f"✓ Emitting join_room event for room {room.id}")
        await sio.emit('join_room', room.id)
    except Exception as e:
        print(f"! Error in connect handler: {str(e)}")
        raise

@sio.event
async def disconnect():
    print("× Disconnected from server")

@sio.event
async def error(data):
    print(f"! Socket.io Error: {data}")

@sio.event
async def join_room_response(data):
    if data.get('status') == 'success':
        print(f"✓ Created/joined room with ID: {data['room_id']}")
        
        # First send a text message
        await sio.emit('send_message', {
            'room_id': data['room_id'],
            'message': 'Hello from test client!',
            'type': 'text'
        })
        print("✓ Test text message sent")
        
        # Then send a test file
        test_file_path = os.path.join(os.path.dirname(__file__), 'test_file.txt')
        with open(test_file_path, 'w') as f:
            f.write('This is a test file for Socket.io upload')
        
        with open(test_file_path, 'rb') as f:
            file_data = base64.b64encode(f.read()).decode('utf-8')
        
        await sio.emit('send_message', {
            'room_id': data['room_id'],
            'message': 'Test file upload',
            'type': 'file',
            'file': {
                'name': 'test_file.txt',
                'type': 'text/plain',
                'data': file_data
            }
        })
        print("✓ Test file message sent")
        
        # Clean up test file
        os.remove(test_file_path)
    else:
        print(f"! Error joining room: {data.get('message', 'Unknown error')}")

@sio.event
async def new_message(data):
    print(f"\n✓ New message received:")
    print(f"  From: {data['sender']}")
    print(f"  Type: {data['type']}")
    print(f"  Content: {data['content']}")
    if data['type'] in ['file', 'image', 'voice']:
        print(f"  File URL: {data.get('file_url')}")
        print(f"  File Name: {data.get('file_name')}")
        print(f"  File Type: {data.get('file_type')}")
        print(f"  File Size: {data.get('file_size')} bytes")

async def main():
    try:
        # Replace with your actual JWT token
        auth = {'token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzM4MDAzNjgxLCJpYXQiOjE3MzgwMDAwODEsImp0aSI6IjE4OWNiOWU0MGMwZjRhMzc5MGRlYTk2NzQ4Y2M4MDBhIiwidXNlcl9pZCI6NH0.3RcB-ZOgj9mj4DAFCLmIN_iJZHNu-7Vwo8K5KQT2Djs'}
        
        # Connect to the server
        await sio.connect('http://localhost:8001', auth=auth)
        
        # Keep the connection alive
        await sio.wait()
    except Exception as e:
        print(f"! Error: {str(e)}")
    finally:
        if sio.connected:
            await sio.disconnect()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n× Shutting down client...") 