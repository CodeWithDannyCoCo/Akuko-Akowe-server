from django.db import models
from django.conf import settings

class ChatRoom(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Chat {self.id} - {', '.join(self.participants.values_list('email', flat=True))}"

class Message(models.Model):
    MESSAGE_TYPES = (
        ('text', 'Text Message'),
        ('file', 'File Attachment'),
        ('voice_call', 'Voice Call'),
        ('video_call', 'Video Call'),  # For future implementation
    )

    MESSAGE_STATUS = (
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    )

    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/', null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    status = models.CharField(max_length=20, choices=MESSAGE_STATUS, default='sent')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.email} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"

class Call(models.Model):
    CALL_STATUS = (
        ('ringing', 'Ringing'),
        ('ongoing', 'Ongoing'),
        ('ended', 'Ended'),
        ('missed', 'Missed'),
    )

    CALL_TYPE = (
        ('voice', 'Voice Call'),
        ('video', 'Video Call'),  # For future implementation
    )

    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='calls')
    initiator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='initiated_calls')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_calls')
    call_type = models.CharField(max_length=10, choices=CALL_TYPE, default='voice')
    status = models.CharField(max_length=10, choices=CALL_STATUS, default='ringing')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True)

    def __str__(self):
        return f"{self.call_type} call from {self.initiator.email} to {self.receiver.email}"
