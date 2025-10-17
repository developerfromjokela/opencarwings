import json

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import translation
from django.utils.module_loading import import_string
from Crypto.Cipher import AES
from Crypto import Random
from urllib.parse import parse_qs
from db.models import Car


class SMSGatewayConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        params = parse_qs(self.scope["query_string"].decode("utf8"), keep_blank_values=False)
        if 'device_id' in params:
            device_id = params['device_id'][0]
        elif "X-Device-Id" not in self.scope['headers'] or len(self.scope['headers']['X-Device-Id']) < 1:
            await self.close()
            return
        else:
            device_id = self.scope['headers']['X-Device-Id']

        cars = await sync_to_async(Car.objects.filter)(sms_config__provider='smsgateway', sms_config__device_id=device_id)
        cars_count = await sync_to_async(cars.count)()
        if cars_count == 0:
            await self.close()
            return

        first_car = await sync_to_async(cars.first)()

        try:
            key = bytes.fromhex(first_car.sms_config.get('encryption_key', '').strip())
        except Exception as e:
            print(e)
            await self.close()
            return

        self.user_id = f'sms_{device_id}'
        self.encryption_key = key

        await self.channel_layer.group_add(self.user_id, self.channel_name)
        await self.accept()
        await self.send_encrypted_parcel(text_data=json.dumps({'type': 'connect'}))


    async def send_encrypted_parcel(self, text_data=None, byte_data=None):
        if text_data is None and byte_data is None:
            raise Exception('You must specify either text_data or byte_data!')

        data = byte_data
        if text_data is not None:
            data = text_data.encode('utf-8')

        nonce = Random.new().read(16)

        padding_length = 16 - (len(data) % 16)
        data += bytes([padding_length]) * padding_length

        cipher = AES.new(self.encryption_key, AES.MODE_CBC, nonce)
        encrypted_data = cipher.encrypt(data)
        encrypted_data = nonce+encrypted_data
        await self.send(bytes_data=encrypted_data)

    async def decrypt_received_parcel(self, data):
        try:
            nonce = data[:16]
            cipher = AES.new(self.encryption_key, AES.MODE_GCM, nonce)
            return cipher.decrypt(data[16:])
        except:
            return None

    async def disconnect(self, close_code):
        if hasattr(self, 'user_id'):
            await self.channel_layer.group_discard(self.user_id, self.channel_name)


    async def receive(self, text_data=None, bytes_data=None):
        if text_data is not None and text_data == 'ping':
            await self.send(text_data='pong')

    async def relay_sms(self, message):
        await self.send_encrypted_parcel(text_data=json.dumps({
            'type': 'sms',
            'sms': message['sms'],
            'phone': message['phone'],
        }))

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):

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
        if self.scope.get('lang', None) is not None:
            translation.activate(self.scope['lang'])

        obj_def = await sync_to_async(import_string)(message['object'])
        retrieved_obj = await database_sync_to_async(self.get_obj_query)(obj_def, message['data'])

        serialized_data = await sync_to_async(self.serialize_data)(message['serializer'], retrieved_obj)

        await self.send(text_data=json.dumps({
            'type': message['object_type'],
            'data': serialized_data,
        }))