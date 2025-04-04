from rest_framework import serializers
from db.models import Car, TCUConfiguration, LocationInfo, EVInfo, AlertHistory


class TCUConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TCUConfiguration
        fields = '__all__'


class LocationInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationInfo
        fields = '__all__'


class EVInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = EVInfo
        fields = '__all__'


class AlertHistorySerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display')

    class Meta:
        model = AlertHistory
        fields = ['id', 'type', 'type_display', 'timestamp', 'command_id', 'additional_data']


class CarSerializer(serializers.ModelSerializer):
    tcu_configuration = TCUConfigurationSerializer()
    location = LocationInfoSerializer()
    ev_info = EVInfoSerializer()
    command_type_display = serializers.CharField(source='get_command_type_display')
    command_result_display = serializers.CharField(source='get_command_result_display')

    class Meta:
        model = Car
        fields = '__all__'

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
