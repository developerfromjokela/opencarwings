from typing import Any

from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers, exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from api.models import TokenMetadata
from db.models import User

class AccountDetailSerializer(serializers.ModelSerializer):
    is_command_pin_set = serializers.BooleanField(read_only=True)
    is_2fa_enabled = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = ['is_2fa_enabled', 'is_command_pin_set', 'timezone', 'email_notifications', 'username', 'email', 'units_imperial', 'last_login']

class PinChangeSerializer(serializers.Serializer):
    otp_code = serializers.RegexField(
        required=False, allow_blank=True, max_length=6, regex=r'^[0-9]{6}$'
    )
    old_pin = serializers.RegexField(
        required=False, allow_blank=False, max_length=4, regex=r'^[0-9]{4}$'
    )
    new_pin = serializers.RegexField(
        required=True, allow_blank=False, max_length=4, regex=r'^[0-9]{4}$'
    )
    new_pin_confirm = serializers.RegexField(
        required=True, allow_blank=False, max_length=4, regex=r'^[0-9]{4}$'
    )

    def validate(self, attrs):
        new_pin = attrs.get('new_pin')
        new_pin_confirm = attrs.get('new_pin_confirm')

        if new_pin or new_pin_confirm:
            if new_pin != new_pin_confirm:
                raise serializers.ValidationError({
                    'new_pin_confirm': _('PIN codes do not match.')
                })

        return attrs

class JWTTokenObtainPairSerializer(TokenObtainPairSerializer):
    otp_code = serializers.RegexField(required=False, allow_blank=True, max_length=6, regex=r'^[0-9]{6}$')
    device_type = serializers.CharField(required=False, allow_blank=True, max_length=100)
    device_os = serializers.CharField(required=False, allow_blank=True, max_length=50)
    app_version = serializers.CharField(required=False, allow_blank=True, max_length=50)
    push_notification_key = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def _validate(self, attrs: dict[str, Any]) -> dict[Any, Any]:
        authenticate_kwargs = {
            self.username_field: attrs[self.username_field],
            "password": attrs["password"],
        }
        try:
            authenticate_kwargs["request"] = self.context["request"]
        except KeyError:
            pass

        self.user = authenticate(**authenticate_kwargs)

        if self.user is not None and self.user.is_2fa_enabled():
            if 'otp_code' not in attrs:
                raise exceptions.AuthenticationFailed(
                    "otp_code_missing",
                    "otp_code_missing",
                )

            if not self.user.verify_otp(attrs["otp_code"]):
                raise exceptions.AuthenticationFailed(
                    "otp_code_invalid",
                    "otp_code_invalid",
                )

        if not api_settings.USER_AUTHENTICATION_RULE(self.user):
            raise exceptions.AuthenticationFailed(
                self.error_messages["no_active_account"],
                "no_active_account",
            )

        return {}

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['orig_jti'] = token['jti']
        return token

    def validate(self, attrs: dict[str, Any]) -> dict[str, str]:
        data = self._validate(attrs)

        refresh = self.get_token(self.user)

        data["refresh"] = str(refresh)
        data["access"] = str(refresh.access_token)

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, self.user)

        return data


class APIErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False, allow_blank=True, read_only=True)
    error = serializers.CharField(required=False, allow_blank=True, read_only=True)

class JWTTokenLoginSerializer(TokenRefreshSerializer):
    user_id = serializers.IntegerField(read_only=True, required=False)
    username = serializers.CharField(required=False, allow_blank=True, max_length=16)


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