from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from db.models import Car, AlertHistory, EVInfo, TCUConfiguration, LocationInfo
from ui.serializers import CarSerializer, AlertHistoryFullSerializer


@receiver(post_save, sender=Car)
def broadcast_car_update(sender, instance, created, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notif_{instance.owner.id}_user',
        {
            'type': 'object_update',
            'object_type': 'car',
            'serializer': CarSerializer.__module__+'.'+CarSerializer.__name__,
            'object': Car.__module__+'.'+Car.__name__,
            'data': instance.pk
        }
    )

@receiver(post_save, sender=EVInfo)
def broadcast_car_evinfo_update(sender, instance, created, **kwargs):
    if created:
        return

    channel_layer = get_channel_layer()
    try:
        car = Car.objects.get(ev_info_id=instance.id)
        async_to_sync(channel_layer.group_send)(
            f'notif_{car.owner.id}_user',
            {
                'type': 'object_update',
                'object_type': 'ev_info',
                'serializer': CarSerializer.__module__ + '.' + CarSerializer.__name__,
                'object': Car.__module__ + '.' + Car.__name__,
                'data': car.pk
            }
        )
    except Car.DoesNotExist:
        pass

@receiver(post_save, sender=TCUConfiguration)
def broadcast_car_tcuconf_update(sender, instance, created, **kwargs):
    if created:
        return

    channel_layer = get_channel_layer()
    try:
        car = Car.objects.get(tcu_configuration_id=instance.id)
        async_to_sync(channel_layer.group_send)(
            f'notif_{car.owner.id}_user',
            {
                'type': 'object_update',
                'object_type': 'tcu_configuration',
                'serializer': CarSerializer.__module__ + '.' + CarSerializer.__name__,
                'object': Car.__module__ + '.' + Car.__name__,
                'data': car.pk
            }
        )
    except Car.DoesNotExist:
        pass


@receiver(post_save, sender=LocationInfo)
def broadcast_car_locinfo_update(sender, instance, created, **kwargs):
    if created:
        return

    channel_layer = get_channel_layer()
    try:
        car = Car.objects.get(location_id=instance.id)
        async_to_sync(channel_layer.group_send)(
            f'notif_{car.owner.id}_user',
            {
                'type': 'object_update',
                'object_type': 'location',
                'serializer': CarSerializer.__module__ + '.' + CarSerializer.__name__,
                'object': Car.__module__ + '.' + Car.__name__,
                'data': car.pk
            }
        )
    except Car.DoesNotExist:
        pass

@receiver(post_save, sender=AlertHistory)
def broadcast_new_alert(sender, instance, created, **kwargs):
    if not created:
        return
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notif_{instance.car.owner.id}_user',
        {
            'type': 'object_update',
            'object_type': 'alert',
            'serializer': AlertHistoryFullSerializer.__module__ + '.' + AlertHistoryFullSerializer.__name__,
            'object': AlertHistory.__module__ + '.' + AlertHistory.__name__,
            'data': instance.pk
        }
    )