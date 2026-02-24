import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import WebsiteOrder

class WebsiteGenerationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        self.room_group_name = f'order_{self.order_id}'

        # TODO: Add auth verification here if needed
        # For now, allow connection
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket (frontend -> backend)
    # Not needed for this one-way stream, but standard to include
    async def receive(self, text_data):
        pass

    # Receive message from room group (Celery -> backend -> frontend)
    async def generation_message(self, event):
        message = event['message']
        message_type = event.get('msg_type', 'token')

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': message_type,
            'token': message if message_type == 'token' else None,
            'message': message if message_type == 'status' else None,
            'preview_url': event.get('preview_url')
        }))
