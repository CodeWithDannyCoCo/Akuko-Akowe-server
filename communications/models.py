from django.db import models
from django.conf import settings

class ChatRoom(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        room_name = self.name or f"Chat {self.id}"
        return f"{room_name} - {', '.join(self.participants.values_list('email', flat=True))}"

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('voice', 'Voice'),
    ]
    
    MESSAGE_STATUS = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    ]
    
    chat_room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    attachment = models.FileField(upload_to='chat_attachments/%Y/%m/%d/', null=True, blank=True)
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)  # Size in bytes
    file_type = models.CharField(max_length=100, null=True, blank=True)  # MIME type
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    status = models.CharField(max_length=10, choices=MESSAGE_STATUS, default='sent')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.sender.email} - {self.message_type} - {self.created_at}"
    
    def get_attachment_url(self):
        if self.attachment:
            return self.attachment.url
        return None

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
