from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from api.models import TokenMetadata


class JWTTokenObtainPairSerializer(TokenObtainPairSerializer):
    device_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    device_os = serializers.CharField(required=False, allow_blank=True, max_length=50)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=50)
    push_notification_key = serializers.CharField(required=False, allow_blank=True, max_length=500)



class TokenMetadataUpdateSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True, max_length=500)
    device_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    device_os = serializers.CharField(required=False, allow_blank=True, max_length=50)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=50)
    push_notification_key = serializers.CharField(required=False, allow_blank=True, max_length=500)

class TokenMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenMetadata
        fields = ('device_type', 'device_os', 'app_version', 'push_notification_key', 'user_agent', 'last_used_at')