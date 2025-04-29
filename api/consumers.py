import json

from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if not self.scope['user'].is_authenticated or self.scope['user'].is_anonymous:
            await self.close()

        self.user_id = f'notif_{self.scope["user"].id}_user'

        await self.channel_layer.group_add(self.user_id, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'listen', 'data': True}))


    async def disconnect(self, close_code):
        if hasattr(self, 'user_id'):
            await self.channel_layer.group_discard(self.user_id, self.channel_name)


    async def receive(self, text_data, bytes_data):
        pass

    async def object_update(self, message):
        await self.send(text_data=json.dumps({
            'type': message['object_type'],
            'data': message['data'],
        }))