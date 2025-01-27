import asyncio
import socketio
import json
import os
import django
from datetime import datetime, timedelta
import jwt
from django.conf import settings

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'blog_api.settings')
django.setup()

from django.contrib.auth import get_user_model
from communications.models import ChatRoom, Call

User = get_user_model()

# Create two Socket.io clients for caller and receiver
caller_sio = socketio.AsyncClient()
receiver_sio = socketio.AsyncClient()

# Store session data
call_data = {}

# Caller events
@caller_sio.event
async def connect():
    print("✓ Caller connected to Socket.io server!")

@caller_sio.event
async def disconnect():
    print("× Caller disconnected from server")
    if 'call_id' in call_data:
        print(f"! Call {call_data['call_id']} ended due to disconnection")

@caller_sio.event
async def error(data):
    print(f"! Caller error: {data}")

@caller_sio.event
async def call_response(data):
    print(f"✓ Call {data['status']} by receiver")
    if data['status'] == 'accepted':
        # Send WebRTC offer after call is accepted
        await caller_sio.emit('webrtc_offer', {
            'call_id': data['call_id'],
            'offer': {
                'type': 'offer',
                'sdp': 'v=0\r\n...(dummy SDP for testing)...'
            }
        })
        print("✓ Sent WebRTC offer")

@caller_sio.event
async def webrtc_answer(data):
    print(f"✓ Received WebRTC answer for call {data['call_id']}")
    # In a real implementation, this would set the remote description

@caller_sio.event
async def webrtc_ice_candidate(data):
    print(f"✓ Received ICE candidate for call {data['call_id']}")
    # In a real implementation, this would add the ICE candidate

@caller_sio.event
async def connect_error(data):
    print(f"Caller connection error: {data}")

@caller_sio.event
async def call_ended(data):
    print(f"✓ Call ended. Duration: {data['duration']} seconds")

@caller_sio.event
async def call_accepted(data):
    print(f"✓ Call accepted by {data['receiver_email']}")
    # Store ICE config for WebRTC connection
    rtc_config = data['rtc_config']
    print("✓ Received ICE configuration")
    
    # Create WebRTC offer
    offer = {
        'type': 'offer',
        'sdp': 'v=0\r\n...'  # Simulated SDP for testing
    }
    
    await caller_sio.emit('webrtc_offer', {
        'call_id': data['call_id'],
        'offer': offer
    })
    print("✓ Sent WebRTC offer")

# Receiver events
@receiver_sio.event
async def connect():
    print("✓ Receiver connected to Socket.io server!")

@receiver_sio.event
async def disconnect():
    print("× Receiver disconnected from server")
    if 'call_id' in call_data:
        print(f"! Call {call_data['call_id']} ended due to disconnection")

@receiver_sio.event
async def error(data):
    print(f"! Receiver error: {data}")

@receiver_sio.event
async def connect_error(data):
    print(f"Receiver connection error: {data}")

@receiver_sio.event
async def incoming_call(data):
    print(f"✓ Incoming call from {data['caller_email']}")
    # Store ICE config for WebRTC connection
    rtc_config = data['rtc_config']
    print("✓ Received ICE configuration")
    
    # Accept the call
    await receiver_sio.emit('call_response', {
        'call_id': data['call_id'],
        'response': 'accept'
    })
    print("✓ Call accepted")

@receiver_sio.event
async def webrtc_offer(data):
    print(f"✓ Received WebRTC offer from {data['caller']}")
    # Send WebRTC answer
    await receiver_sio.emit('webrtc_answer', {
        'call_id': data['call_id'],
        'answer': {
            'type': 'answer',
            'sdp': 'v=0\r\n...(dummy SDP for testing)...'
        }
    })
    print("✓ Sent WebRTC answer")
    
    # Send an ICE candidate
    await receiver_sio.emit('webrtc_ice_candidate', {
        'call_id': data['call_id'],
        'candidate': {
            'candidate': 'candidate:1234567890 1 udp 2122260223 192.168.1.1 54321 typ host',
            'sdpMLineIndex': 0,
            'sdpMid': '0'
        }
    })
    print("✓ Sent ICE candidate")

@receiver_sio.event
async def call_ended(data):
    print(f"✓ Call ended. Duration: {data['duration']} seconds")

def generate_jwt_token(user):
    """Generate a valid JWT token for testing"""
    payload = {
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(days=1),
        'iat': datetime.utcnow(),
        'token_type': 'access'
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

async def setup_test():
    """Set up test users and chat room"""
    # Get or create test users
    caller = await User.objects.aget_or_create(
        email='caller@test.com',
        defaults={
            'username': 'test_caller',
            'password': 'testpass123'
        }
    )
    receiver = await User.objects.aget_or_create(
        email='receiver@test.com',
        defaults={
            'username': 'test_receiver',
            'password': 'testpass123'
        }
    )
    
    # Get or create test chat room
    room = await ChatRoom.objects.aget_or_create(
        name='Test Voice Call Room',
        defaults={'is_active': True}
    )
    
    # Add users to room
    await room[0].participants.aset([caller[0], receiver[0]])

async def main():
    try:
        caller, receiver, room = await setup_test()
        print(f"✓ Set up test room: {room.name}")
        
        # Connect both clients with auth headers
        await caller_sio.connect(
            'http://localhost:8001',
            auth={'token': generate_jwt_token(caller)},
            wait_timeout=10
        )
        await receiver_sio.connect(
            'http://localhost:8001',
            auth={'token': generate_jwt_token(receiver)},
            wait_timeout=10
        )
        
        # Join the room - send just the room ID number
        await caller_sio.emit('join_room', room.id)
        await receiver_sio.emit('join_room', room.id)
        
        # Initiate call
        await caller_sio.emit('call_request', {
            'room_id': room.id,
            'receiver_id': receiver.id
        })
        print("✓ Call initiated")
        
        # Keep the connection alive until interrupted
        while True:
            try:
                # Check connection status every 5 seconds
                if not caller_sio.connected or not receiver_sio.connected:
                    print("! Connection lost")
                    break
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                print("\n✓ Test interrupted, ending call...")
                # End the call gracefully
                if 'call_id' in call_data:
                    await caller_sio.emit('call_end', {
                        'call_id': call_data['call_id']
                    })
                    print("✓ Call ended")
                break
        
    except Exception as e:
        print(f"Error in test: {str(e)}")
    finally:
        # Clean up
        if caller_sio.connected:
            await caller_sio.disconnect()
        if receiver_sio.connected:
            await receiver_sio.disconnect()
        print("✓ Test completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error running test: {str(e)}") 