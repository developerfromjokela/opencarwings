from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class JWTTokenObtainPairSerializer(TokenObtainPairSerializer):
    device_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    device_os = serializers.CharField(required=False, allow_blank=True, max_length=50)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=50)
    push_notification_key = serializers.CharField(required=False, allow_blank=True, max_length=500)