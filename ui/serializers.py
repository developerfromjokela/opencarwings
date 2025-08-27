from rest_framework import serializers
from db.models import Car, TCUConfiguration, LocationInfo, EVInfo, AlertHistory, SendToCarLocation


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
    send_to_car_location = SendToCarLocationSerializer()
    command_type_display = serializers.CharField(source='get_command_type_display')
    command_result_display = serializers.CharField(source='get_command_result_display')

    class Meta:
        model = Car
        fields = '__all__'

class CarUpdatingSerializer(serializers.ModelSerializer):
    send_to_car_location = SendToCarLocationSerializer(required=False, allow_null=True)
    ev_info = EVInfoUpdatingSerializer(required=False)
    class Meta:
        model = Car
        fields = ['color', 'sms_config', 'nickname', 'send_to_car_location', 'ev_info', 'tcu_model', 'tcu_serial',
                  'iccid', 'disable_auth', 'periodic_refresh', 'periodic_refresh_running']

    def update(self, instance, validated_data):
        if 'send_to_car_location' in validated_data:
            if validated_data.get('send_to_car_location', None) is None:
                instance.send_to_car_location = None
            else:
                if instance.send_to_car_location is None:
                    instance.send_to_car_location = SendToCarLocation()
                instance.send_to_car_location.name = validated_data.get('send_to_car_location').get('name')
                instance.send_to_car_location.lat = validated_data.get('send_to_car_location').get('lat')
                instance.send_to_car_location.lon = validated_data.get('send_to_car_location').get('lon')
                instance.send_to_car_location.save()

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
    send_to_car_location = SendToCarLocationSerializer()
    class Meta:
        model = Car
        fields = ('vin', 'last_connection', 'nickname', 'ev_info', 'location', 'send_to_car_location')

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
