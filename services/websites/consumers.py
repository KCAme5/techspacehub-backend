import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import WebsiteOrder


class WebsiteGenerationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.order_id = self.scope["url_route"]["kwargs"]["order_id"]
        self.room_group_name = f"order_{self.order_id}"

        # TODO: Add auth verification here if needed
        # For now, allow connection

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    # Receive message from WebSocket (frontend -> backend)
    # Not needed for this one-way stream, but standard to include
    async def receive(self, text_data):
        pass

    # Receive message from room group (Celery -> backend -> frontend)
    async def generation_message(self, event):
        message = event["message"]
        message_type = event.get("msg_type", "token")

        # Build response based on message type
        response = {
            "type": message_type,
            "message": message,
        }

        # Handle different message types
        if message_type == "token":
            response["token"] = message
        elif message_type == "status":
            response["status"] = message
        elif message_type == "code_update":
            response["code_chunk"] = message
        elif message_type == "complete":
            response["preview_url"] = event.get("preview_url")
        elif message_type == "revision_complete":
            response["preview_url"] = event.get("preview_url")
            response["status"] = "Revision complete!"

        # Send message to WebSocket
        await self.send(text_data=json.dumps(response))
