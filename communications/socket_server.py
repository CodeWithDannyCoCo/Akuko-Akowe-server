import socketio
import jwt
import base64
import os
import mimetypes
from django.conf import settings
from .models import ChatRoom, Message, Call
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone
from .utils import get_turn_credentials

User = get_user_model()

# File upload settings
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_FILE_TYPES = {
    'image': ['image/jpeg', 'image/png', 'image/gif'],
    'file': ['application/pdf', 'text/plain', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
    'voice': ['audio/wav', 'audio/mpeg', 'audio/webm']
}

# Create a Socket.io server
sio = socketio.AsyncServer(
    async_mode='aiohttp',
    cors_allowed_origins=settings.SOCKETIO['CORS_ALLOWED_ORIGINS']
)

# JWT authentication middleware
async def authenticate_user(token):
    try:
        # Verify the JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        user = await User.objects.aget(id=payload['user_id'])
        return user
    except (jwt.InvalidTokenError, User.DoesNotExist):
        return None

@sio.event
async def connect(sid, environ, auth):
    """Handle client connection"""
    print(f"Connection attempt from {sid}")
    if not auth or 'token' not in auth:
        print(f"Authentication failed: No token provided for {sid}")
        return False
    
    user = await authenticate_user(auth['token'])
    if not user:
        print(f"Authentication failed: Invalid token for {sid}")
        return False
    
    # Store user information in the session
    await sio.save_session(sid, {'user_id': user.id, 'user_email': user.email})
    # Add user to their personal room for direct messages
    await sio.enter_room(sid, f'user_{user.id}')
    print(f"User {user.email} connected with sid {sid}")
    return True

@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    await sio.disconnect(sid)

@sio.event
async def join_room(sid, room_id):
    """Handle room joining"""
    print(f"Join room request received - SID: {sid}, Room: {room_id}")
    session = await sio.get_session(sid)
    user_id = session['user_id']
    
    try:
        # Check if user is a participant of the room
        room = await ChatRoom.objects.aget(id=room_id, participants__id=user_id)
        await sio.enter_room(sid, f'room_{room_id}')
        print(f"User {session['user_email']} joined room {room_id}")
        await sio.emit('join_room_response', {'status': 'success', 'room_id': room_id}, room=sid)
        return {'status': 'success', 'room_id': room_id}
    except ChatRoom.DoesNotExist:
        error_msg = 'Room not found or access denied'
        print(f"Join room failed - SID: {sid}, Room: {room_id} - {error_msg}")
        await sio.emit('join_room_response', {'status': 'error', 'message': error_msg}, room=sid)
        return {'status': 'error', 'message': error_msg}

@sio.event
async def leave_room(sid, room_id):
    """Handle room leaving"""
    await sio.leave_room(sid, f'room_{room_id}')
    return {'status': 'success', 'room_id': room_id}

@sio.event
async def send_message(sid, data):
    """Handle message sending"""
    print(f"Message received - SID: {sid}, Room: {data.get('room_id')}, Type: {data.get('type')}")
    session = await sio.get_session(sid)
    user_id = session['user_id']
    room_id = data.get('room_id')
    content = data.get('message', '')
    message_type = data.get('type', 'text')
    
    try:
        # Save message to database
        room = await ChatRoom.objects.aget(id=room_id, participants__id=user_id)
        user = await User.objects.aget(id=user_id)
        
        message_data = {
            'chat_room': room,
            'sender': user,
            'content': content,
            'message_type': message_type
        }

        # Handle file attachments
        if message_type in ['file', 'image', 'voice']:
            file_data = data.get('file')
            if not file_data:
                return {'status': 'error', 'message': 'No file data provided'}
            
            # Check file type
            file_type = file_data.get('type', '')
            if not file_type or file_type not in ALLOWED_FILE_TYPES.get(message_type, []):
                return {
                    'status': 'error', 
                    'message': f'Unsupported file type. Allowed types for {message_type}: {", ".join(ALLOWED_FILE_TYPES[message_type])}'
                }
            
            # Decode base64 file data
            try:
                file_content = base64.b64decode(file_data['data'])
                file_size = len(file_content)
                
                # Check file size
                if file_size > MAX_FILE_SIZE:
                    return {
                        'status': 'error',
                        'message': f'File too large. Maximum size allowed: {MAX_FILE_SIZE/1024/1024}MB'
                    }
                
                file_name = file_data['name']
                
                # Create file from decoded data
                file_content = ContentFile(file_content, name=file_name)
                
                # Add file data to message
                message_data.update({
                    'attachment': file_content,
                    'file_name': file_name,
                    'file_type': file_type,
                    'file_size': file_size
                })
            except Exception as e:
                print(f"File processing error: {str(e)}")
                return {'status': 'error', 'message': 'Failed to process file'}
        
        message = await Message.objects.acreate(**message_data)
        
        # Prepare broadcast data
        broadcast_data = {
            'message_id': message.id,
            'room_id': room_id,
            'sender': user.email,
            'content': content,
            'type': message_type,
            'timestamp': message.created_at.isoformat()
        }
        
        # Add file information if present
        if message.attachment:
            broadcast_data.update({
                'file_url': message.get_attachment_url(),
                'file_name': message.file_name,
                'file_type': message.file_type,
                'file_size': message.file_size
            })
        
        print(f"Broadcasting message to room_{room_id}: {broadcast_data}")
        await sio.emit('new_message', broadcast_data, room=f'room_{room_id}')
        
        return {'status': 'success', 'message_id': message.id}
    except ChatRoom.DoesNotExist:
        error_msg = 'Room not found or access denied'
        print(f"Send message failed - SID: {sid}, Room: {room_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg}
    except Exception as e:
        error_msg = f'Failed to send message: {str(e)}'
        print(f"Send message failed - SID: {sid}, Room: {room_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg}

@sio.event
async def typing_start(sid, room_id):
    """Handle typing indicator start"""
    session = await sio.get_session(sid)
    await sio.emit('user_typing_start', {
        'user': session['user_email']
    }, room=f'room_{room_id}', skip_sid=sid)

@sio.event
async def typing_stop(sid, room_id):
    """Handle typing indicator stop"""
    session = await sio.get_session(sid)
    await sio.emit('user_typing_stop', {
        'user': session['user_email']
    }, room=f'room_{room_id}', skip_sid=sid)

# Voice call events
@sio.event
async def call_request(sid, data):
    """Handle voice call request"""
    session = await sio.get_session(sid)
    user_id = session['user_id']
    room_id = data.get('room_id')
    receiver_id = data.get('receiver_id')
    
    try:
        # Verify room and participants
        room = await ChatRoom.objects.aget(id=room_id, participants__id=user_id)
        caller = await User.objects.aget(id=user_id)
        receiver = await User.objects.aget(id=receiver_id)
        
        if not (await room.participants.filter(id__in=[caller.id, receiver.id]).acount() == 2):
            await sio.emit('error', {'message': 'Invalid participants'}, room=sid)
            return
        
        # Create call record
        call = await Call.objects.acreate(
            chat_room=room,
            initiator=caller,
            receiver=receiver,
            call_type='voice',
            status='requesting'
        )
        
        # Store call ID in session for later use
        session[sid]['current_call'] = call.id
        
        # Get TURN credentials
        turn_config = get_turn_credentials()
        if not turn_config:
            # Fall back to STUN only if TURN credentials are unavailable
            turn_config = settings.WEBRTC_CONFIG['iceServers'][0]
        
        # Update WebRTC config with current TURN credentials
        rtc_config = settings.WEBRTC_CONFIG.copy()
        rtc_config['iceServers'] = [
            settings.WEBRTC_CONFIG['iceServers'][0],  # STUN servers
            turn_config  # TURN server with current credentials
        ]

        # Emit the incoming call event with the updated RTC config
        await sio.emit('incoming_call', {
            'call_id': call.id,
            'caller_id': session['user_id'],
            'caller_email': session['user_email'],
            'room_id': room_id,
            'rtc_config': rtc_config
        }, room=f'user_{receiver_id}')
        
        print(f"Emitting call request to user_{receiver_id}")
        
    except Exception as e:
        print(f"Error in call_request: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def call_response(sid, data):
    """Handle call accept/reject response"""
    session = await sio.get_session(sid)
    call_id = data.get('call_id')
    response = data.get('response')  # 'accept' or 'reject'
    
    try:
        call = await Call.objects.aget(id=call_id)
        caller_id = call.initiator.id
        
        if response == 'accept':
            call.status = 'ongoing'
            await call.asave()
            
            # Send acceptance with ICE configuration
            await sio.emit('call_accepted', {
                'call_id': call.id,
                'receiver_id': session[sid]['user_id'],
                'receiver_email': session[sid]['user_email'],
                'rtc_config': settings.WEBRTC_CONFIG
            }, room=f'user_{caller_id}')
        else:
            call.status = 'rejected'
            call.ended_at = timezone.now()
            await call.asave()
            
            await sio.emit('call_rejected', {
                'call_id': call.id,
                'reason': data.get('reason', 'Call rejected by user')
            }, room=f'user_{caller_id}')
            
        return {'status': 'success'}
    except Exception as e:
        print(f"Error in call_response: {str(e)}")
        await sio.emit('error', {'message': str(e)}, room=sid)

@sio.event
async def call_end(sid, data):
    """Handle call end"""
    session = await sio.get_session(sid)
    call_id = data.get('call_id')
    
    try:
        call = await Call.objects.aget(id=call_id)
        call.status = 'ended'
        call.ended_at = timezone.now()
        call.duration = call.ended_at - call.started_at
        await call.asave()
        
        # Notify other participant
        other_user_id = call.receiver_id if session['user_id'] == call.initiator_id else call.initiator_id
        await sio.emit('call_ended', {
            'call_id': call_id,
            'duration': call.duration.total_seconds()
        }, room=f'user_{other_user_id}')
        
        return {'status': 'success'}
    except Exception as e:
        error_msg = f'Failed to end call: {str(e)}'
        print(f"Call end failed - SID: {sid}, Call: {call_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg}

# WebRTC signaling events
@sio.event
async def webrtc_offer(sid, data):
    """Handle WebRTC offer from caller"""
    session = await sio.get_session(sid)
    call_id = data.get('call_id')
    
    try:
        call = await Call.objects.aget(id=call_id)
        if call.status != 'ongoing':
            return {'status': 'error', 'message': 'Call is not active'}
        
        # Forward the offer to the other participant
        other_user_id = call.receiver_id if session['user_id'] == call.initiator_id else call.initiator_id
        await sio.emit('webrtc_offer', {
            'call_id': call_id,
            'offer': data.get('offer'),
            'caller': session['user_email']
        }, room=f'user_{other_user_id}')
        
        return {'status': 'success'}
    except Exception as e:
        error_msg = f'Failed to process WebRTC offer: {str(e)}'
        print(f"WebRTC offer failed - SID: {sid}, Call: {call_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg}

@sio.event
async def webrtc_answer(sid, data):
    """Handle WebRTC answer from callee"""
    session = await sio.get_session(sid)
    call_id = data.get('call_id')
    
    try:
        call = await Call.objects.aget(id=call_id)
        if call.status != 'ongoing':
            return {'status': 'error', 'message': 'Call is not active'}
        
        # Forward the answer to the other participant
        other_user_id = call.initiator_id if session['user_id'] == call.receiver_id else call.receiver_id
        await sio.emit('webrtc_answer', {
            'call_id': call_id,
            'answer': data.get('answer')
        }, room=f'user_{other_user_id}')
        
        return {'status': 'success'}
    except Exception as e:
        error_msg = f'Failed to process WebRTC answer: {str(e)}'
        print(f"WebRTC answer failed - SID: {sid}, Call: {call_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg}

@sio.event
async def webrtc_ice_candidate(sid, data):
    """Handle ICE candidate from either participant"""
    session = await sio.get_session(sid)
    call_id = data.get('call_id')
    
    try:
        call = await Call.objects.aget(id=call_id)
        if call.status != 'ongoing':
            return {'status': 'error', 'message': 'Call is not active'}
        
        # Forward the ICE candidate to the other participant
        other_user_id = call.receiver_id if session['user_id'] == call.initiator_id else call.initiator_id
        await sio.emit('webrtc_ice_candidate', {
            'call_id': call_id,
            'candidate': data.get('candidate')
        }, room=f'user_{other_user_id}')
        
        return {'status': 'success'}
    except Exception as e:
        error_msg = f'Failed to process ICE candidate: {str(e)}'
        print(f"ICE candidate failed - SID: {sid}, Call: {call_id} - {error_msg}")
        return {'status': 'error', 'message': error_msg} 