from django.contrib import admin
from .models import ChatRoom, Message, Call

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('participants__email',)
    date_hierarchy = 'created_at'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'chat_room', 'message_type', 'status', 'created_at')
    list_filter = ('message_type', 'status', 'created_at')
    search_fields = ('content', 'sender__email')
    date_hierarchy = 'created_at'

@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ('initiator', 'receiver', 'call_type', 'status', 'started_at', 'duration')
    list_filter = ('call_type', 'status', 'started_at')
    search_fields = ('initiator__email', 'receiver__email')
    date_hierarchy = 'started_at'
