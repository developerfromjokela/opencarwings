from rest_framework import serializers

from db.models import Car, TCUConfiguration, LocationInfo, EVInfo, AlertHistory, SendToCarLocation, RoutePlan
from tculink.carwings_proto.autodj import ICONS
from tculink.carwings_proto.autodj.channels import get_info_channel_data


class TCUConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TCUConfiguration
        fields = '__all__'


class LocationInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationInfo
        fields = '__all__'

class SendToCarLocationSerializer(serializers.ModelSerializer):
    lat = serializers.DecimalField(max_digits=20, decimal_places=10)
    lon = serializers.DecimalField(max_digits=20, decimal_places=10)
    name = serializers.CharField(max_length=32)
    class Meta:
        model = SendToCarLocation
        fields = '__all__'

class RoutePlanSerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=31)
    start_name = serializers.CharField(max_length=30)
    start_lat = serializers.DecimalField(max_digits=20, decimal_places=10)
    start_lon = serializers.DecimalField(max_digits=20, decimal_places=10)
    finish_name = serializers.CharField(max_length=30)
    finish_lat = serializers.DecimalField(max_digits=20, decimal_places=10)
    finish_lon = serializers.DecimalField(max_digits=20, decimal_places=10)
    point1_name = serializers.CharField(max_length=30, allow_blank=True, allow_null=True, required=False)
    point1_lat = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point1_lon = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point2_name = serializers.CharField(max_length=30, allow_blank=True, allow_null=True, required=False)
    point2_lat = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point2_lon = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point3_name = serializers.CharField(max_length=30, allow_blank=True, allow_null=True, required=False)
    point3_lat = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point3_lon = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point4_name = serializers.CharField(max_length=30, allow_blank=True, allow_null=True, required=False)
    point4_lat = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point4_lon = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point5_name = serializers.CharField(max_length=30, allow_blank=True, allow_null=True, required=False)
    point5_lat = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    point5_lon = serializers.DecimalField(max_digits=20, decimal_places=10, allow_null=True, required=False)
    class Meta:
        model = RoutePlan
        fields = '__all__'

# for update
class SendToCarLocationGenericSerializer(serializers.Serializer):
    lat = serializers.DecimalField(max_digits=20, decimal_places=10)
    lon = serializers.DecimalField(max_digits=20, decimal_places=10)
    name = serializers.CharField(max_length=32)

class EVInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EVInfo
        fields = '__all__'

class EVInfoUpdatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = EVInfo
        fields = ['force_soc_display']

class AlertHistorySerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display')

    class Meta:
        model = AlertHistory
        fields = ['id', 'type', 'type_display', 'timestamp', 'command_id', 'additional_data']


class CarSerializer(serializers.ModelSerializer):
    tcu_configuration = TCUConfigurationSerializer()
    location = LocationInfoSerializer()
    ev_info = EVInfoSerializer()
    send_to_car_location = SendToCarLocationSerializer(many=True)
    route_plans = RoutePlanSerializer(many=True)
    command_type_display = serializers.CharField(source='get_command_type_display')
    command_result_display = serializers.CharField(source='get_command_result_display')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['send_to_car_location_all'] = SendToCarLocationSerializer(many=True).to_representation(instance.send_to_car_location)
        if instance.send_to_car_location.count() > 0:
            data['send_to_car_location'] = SendToCarLocationSerializer().to_representation(
                instance.send_to_car_location.order_by('-created_at').first())
        else:
            data["send_to_car_location"] = None
        return data

    class Meta:
        model = Car
        fields = '__all__'

class CarUpdatingSerializer(serializers.ModelSerializer):
    send_to_car_location = SendToCarLocationSerializer(required=False, allow_null=True)
    send_to_car_location_all = SendToCarLocationSerializer(required=False, allow_null=True, many=True)
    route_plans = RoutePlanSerializer(many=True, required=False)
    ev_info = EVInfoUpdatingSerializer(required=False)
    favorite_channels = serializers.JSONField(required=False)
    custom_channels = serializers.JSONField(required=False)
    class Meta:
        model = Car
        fields = [ 'send_to_car_location', 'send_to_car_location_all', 'ev_info', 'route_plans', 'favorite_channels', 'custom_channels' ]

    def update(self, instance, validated_data):
        if 'send_to_car_location' in validated_data:
            if validated_data.get('send_to_car_location', None) is not None:
                send_to_car_location = SendToCarLocation()
                send_to_car_location.name = validated_data.get('send_to_car_location').get('name')
                send_to_car_location.lat = validated_data.get('send_to_car_location').get('lat')
                send_to_car_location.lon = validated_data.get('send_to_car_location').get('lon')
                send_to_car_location.save()

                instance.send_to_car_location.add(send_to_car_location)

                if instance.send_to_car_location.count() > 6:
                    oldest_item = instance.send_to_car_location.order_by('created_at').first()
                    if oldest_item:
                        instance.send_to_car_location.remove(oldest_item)
                        oldest_item.delete()
        elif 'send_to_car_location_all' in validated_data:
            if validated_data.get('send_to_car_location_all', None) is not None:
                instance.send_to_car_location.all().delete()
                for item in validated_data['send_to_car_location_all'][:6]:
                    send_to_car_location = SendToCarLocation()
                    for key, value in item.items():
                        if hasattr(send_to_car_location, key):
                            setattr(send_to_car_location, key, value)
                    send_to_car_location.save()

                    instance.send_to_car_location.add(send_to_car_location)

        if 'route_plans' in validated_data:
            if validated_data.get('route_plans', None) is not None:
                instance.route_plans.all().delete()
                for item in validated_data['route_plans'][:5]:
                    route_plan = RoutePlan()
                    route_plan.name = item.get('name')
                    for key, value in item.items():
                        if hasattr(route_plan, key):
                            setattr(route_plan, key, value)
                    route_plan.save()
                    instance.route_plans.add(route_plan)

        if 'custom_channels' in validated_data and isinstance(validated_data['custom_channels'], dict):
            chandict = validated_data['custom_channels']
            validated_customchandict = {}
            for i in range(16):
                i = str(i)
                if i in chandict:
                    chanitem = chandict[i]
                    print(chanitem)
                    if 'name' in chanitem and 'icon' in chanitem and 'url' in chanitem:
                        validated_customchandict[i] = {
                            'name': chanitem['name'][:30],
                            'icon': next((x[0] for x in list(ICONS.values()) if x[0] == chanitem['icon']), "info.png"),
                            'url': chanitem['url'][:255],
                            'location': chanitem.get('location', False) or False,
                        }
            instance.custom_channels = validated_customchandict
        if 'favorite_channels' in validated_data and isinstance(validated_data['favorite_channels'], dict):
            chandict = validated_data['favorite_channels']
            all_chans, _ = get_info_channel_data(instance)
            validated_chandict = {}
            for i in range(2, 16+1):
                i = str(i)
                if i in chandict:
                    chan_id = chandict[i]
                    if next((x for x in all_chans if x['id'] == chan_id), None) is not None:
                        validated_chandict[i] = chan_id
            instance.favorite_channels = validated_chandict

        if validated_data.get('ev_info', None) is not None:
            if instance.ev_info is None:
                instance.ev_info = EVInfo()
            instance.ev_info.force_soc_display = validated_data.get('ev_info').get('force_soc_display')
            instance.ev_info.save()
        instance.save()
        return instance

class CarSerializerList(serializers.ModelSerializer):
    ev_info = EVInfoSerializer()
    location = LocationInfoSerializer()
    class Meta:
        model = Car
        fields = ('vin', 'last_connection', 'nickname', 'ev_info', 'location')

class CommandResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    car = CarSerializer()

class CommandErrorSerializer(serializers.Serializer):
    error = serializers.CharField()

class StatusSerializer(serializers.Serializer):
    status = serializers.BooleanField(required=True)
    cause = serializers.CharField(required=False)

class AlertHistoryFullSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display')
    car = CarSerializer()

    class Meta:
        model = AlertHistory
        fields = ['id', 'type', 'type_display', 'timestamp', 'command_id', 'additional_data', 'car']

class MapLinkResolverInputSerializer(serializers.Serializer):
    url = serializers.CharField(max_length=1024)

class MapLinkResolvedLocation(serializers.Serializer):
    lat = serializers.DecimalField(max_digits=20, decimal_places=10)
    lon = serializers.DecimalField(max_digits=20, decimal_places=10)
    name = serializers.CharField()
    address = serializers.CharField()

class MapLinkResolverResponseSerializer(StatusSerializer):
    location = MapLinkResolvedLocation(allow_null=True, required=False)
