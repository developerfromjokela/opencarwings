from rest_framework import serializers

from db.models import CRMLatest, CRMLifetime


class CRMLatestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CRMLatest
        fields = ['phone_contacts', 'navi_points_saved', 'odometer', 'last_updated']

class CRMLifetimeSerializer(serializers.ModelSerializer):
    consumption = serializers.FloatField(default=0, label="Lifetime Consumption Wh")
    regen = serializers.FloatField(default=0, label="Lifetime Regen Wh")
    average_speed = serializers.FloatField(default=0, label="kph")
    aircon_usage = serializers.BigIntegerField(default=0, label="seconds")
    headlight_on_time = serializers.BigIntegerField(default=0, label="seconds")
    running_time = serializers.BigIntegerField(default=0, label="seconds")

    class Meta:
        model = CRMLifetime
        fields = '__all__'

    def to_representation(self, instance):
        super_obj = super().to_representation(instance)
        super_obj["consumption"] = super_obj["consumption"] / 1000
        super_obj["regen"] = super_obj["regen"] / 100000
        return super_obj