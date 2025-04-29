import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import translation
from django.utils.module_loading import import_string


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(self.scope['lang'])

        if not self.scope['user'].is_authenticated or self.scope['user'].is_anonymous:
            await self.close()

        if self.scope.get('lang', None) is not None:
            translation.activate(self.scope['lang'])

        self.user_id = f'notif_{self.scope["user"].id}_user'

        await self.channel_layer.group_add(self.user_id, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({'type': 'listen', 'data': True}))


    async def disconnect(self, close_code):
        if hasattr(self, 'user_id'):
            await self.channel_layer.group_discard(self.user_id, self.channel_name)


    async def receive(self, text_data, bytes_data):
        pass

    def get_obj_query(self, obj, id):
        return obj.objects.get(id=id)

    def serialize_data(self, serializer_name, data):
        serializer_obj = import_string(serializer_name)
        serializer_instance = serializer_obj(data)
        return serializer_instance.data

    async def object_update(self, message):
        print(self.scope['lang'])
        if self.scope.get('lang', None) is not None:
            translation.activate(self.scope['lang'])

        obj_def = await sync_to_async(import_string)(message['object'])
        retrieved_obj = await database_sync_to_async(self.get_obj_query)(obj_def, message['data'])

        serialized_data = await sync_to_async(self.serialize_data)(message['serializer'], retrieved_obj)

        await self.send(text_data=json.dumps({
            'type': message['object_type'],
            'data': serialized_data,
        }))