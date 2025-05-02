from random import randint

import django
from django.core.exceptions import ObjectDoesNotExist
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils.translation import gettext_lazy as _
from api.models import TokenMetadata
from api.serializers import JWTTokenObtainPairSerializer, TokenMetadataUpdateSerializer, TokenMetadataSerializer
from tculink.sms import send_using_provider
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, permissions
from rest_framework.decorators import api_view
from rest_framework.generics import get_object_or_404, RetrieveAPIView, UpdateAPIView, DestroyAPIView
from rest_framework.response import Response

from db.models import Car, AlertHistory, COMMAND_TYPES, User
from ui.serializers import CarSerializer, CarSerializerList, AlertHistorySerializer, \
    CommandResponseSerializer, CommandErrorSerializer


class IsCarOwner(permissions.BasePermission):
    # for view permission
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    # for object level permissions
    def has_object_permission(self, request, view, car_obj):
        return car_obj.owner.id == request.user.id



@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['cars'],
    responses={status.HTTP_200_OK: CarSerializer()}
))
@method_decorator(name='put', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CarSerializer(),
    responses={status.HTTP_200_OK: CarSerializer()}
))
@method_decorator(name='patch', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CarSerializer(),
    responses={status.HTTP_204_NO_CONTENT: "Success"}
))
@method_decorator(name='delete', decorator=swagger_auto_schema(
    tags=['cars'],
    responses={status.HTTP_204_NO_CONTENT: "Success"}
))
class CarAPIView(RetrieveAPIView, UpdateAPIView, DestroyAPIView):
    permission_classes = [IsAuthenticated, IsCarOwner]
    queryset = Car.objects.all()
    serializer_class = CarSerializer
    lookup_field = 'vin'


@swagger_auto_schema(
    operation_description="Update token metadata",
    tags=['token'],
    method='post',
    request_body=TokenMetadataUpdateSerializer(),
    responses={
        200: TokenMetadataSerializer(),
        401: 'Not authorized',
        400: CommandErrorSerializer(),
    }
)
@api_view(['POST'])
def update_token_metadata(request):
    try:
        serializer = TokenMetadataUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        refresh_token_str = serializer.validated_data.get("refresh")
        if not refresh_token_str:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Create RefreshToken instance to extract jti
        refresh_token = RefreshToken(refresh_token_str)
        try:
            refresh_token.verify()
        except TokenError:
            return Response({"error": "Invalid refresh token"}, status=status.HTTP_400_BAD_REQUEST)

        jti = refresh_token['jti']

        # Verify the token belongs to the authenticated user by checking TokenMetadata
        try:
            metadata = TokenMetadata.objects.get(token=jti, user=request.user)
        except ObjectDoesNotExist:
            return Response({"error": "Token metadata not found or does not belong to user"}, status=status.HTTP_404_NOT_FOUND)

        device_type = serializer.validated_data.get('device_type', '') or request.headers.get('X-Device-Type', '')
        device_os = serializer.validated_data.get('device_os', '') or request.headers.get('X-Device-OS', '')
        app_version = serializer.validated_data.get('app_version', '') or request.headers.get('X-App-Version', '')
        push_notification_key = serializer.validated_data.get('push_notification_key', '')

        metadata.device_type = device_type
        metadata.device_os = device_os
        metadata.app_version = app_version
        metadata.push_notification_key = push_notification_key
        metadata.save()

        return Response(TokenMetadataSerializer(metadata).data, status=status.HTTP_200_OK)
    except ObjectDoesNotExist:
        return Response({"error": "Token not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    operation_description="Sign out and invalidate tokens",
    tags=['token'],
    method='post',
    request_body=import_string(api_settings.TOKEN_BLACKLIST_SERIALIZER),
    responses={
        200: "Successfully signed out and token revoked",
        401: 'Not authorized',
        400: CommandErrorSerializer(),
    }
)
@api_view(['POST'])
def sign_out(request):
    try:
        refresh_token_str = request.data.get("refresh")
        if not refresh_token_str:
            return Response({"error": "Refresh token is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Create RefreshToken instance to extract jti
        refresh_token = RefreshToken(refresh_token_str)
        jti = refresh_token['jti']

        # Verify the token belongs to the authenticated user by checking TokenMetadata
        try:
            metadata = TokenMetadata.objects.get(token=jti, user=request.user)
        except ObjectDoesNotExist:
            return Response({"error": "Token metadata not found or does not belong to user"}, status=status.HTTP_404_NOT_FOUND)

        # Blacklist the token
        try:
            outstanding_token = OutstandingToken.objects.get(jti=jti)
            BlacklistedToken.objects.create(token=outstanding_token)
        except ObjectDoesNotExist:
            pass

        # Delete the associated TokenMetadata
        metadata.delete()

        return Response({"status": "Successfully signed out and token revoked"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    operation_description="Retrieve a list of cars",
    method='get',
    tags=['cars'],
    responses={
        200: CarSerializerList(many=True),
        401: 'Not authorized',
    }
)
@api_view(['GET'])
def cars_api(request):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = Car.objects.filter(owner=request.user)

    serializer = CarSerializerList(car, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    operation_description="Retrieve a list of alerts for a vehicle",
    method='get',
    tags=['alerts'],
    responses={
        200: AlertHistorySerializer(many=True),
        401: 'Not authorized',
        404: 'Car not found',
    }
)
@api_view(['GET'])
def alerts_api(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = get_object_or_404(Car, vin=vin, owner=request.user)
    alerts = AlertHistory.objects.filter(car=car).order_by('-timestamp')[:25]
    serializer = AlertHistorySerializer(alerts, many=True)
    return Response(serializer.data)


@swagger_auto_schema(
    operation_description="Send a command to your vehicle",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'command_type': openapi.Schema(type=openapi.TYPE_NUMBER, title="Command type", enum=COMMAND_TYPES),
        },
        required=['vin', 'command_type']
    ),
    tags=['cars'],
    method='post',
    responses={
        200: CommandResponseSerializer(),
        401: 'Not authorized',
        404: 'Car not found',
        400: CommandErrorSerializer(),
    }
)
@api_view(['POST'])
def command_api(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    car = get_object_or_404(Car, vin=vin, owner=request.user)
    command_type = request.data.get('command_type')

    try:
        command_type = int(command_type)
        if command_type in dict(COMMAND_TYPES):
            try:
                sms_result = send_using_provider(django.conf.settings.ACTIVATION_SMS_MESSAGE, car.sms_config)
                if not sms_result:
                    raise Exception("Could not send SMS message")
            except Exception as e:
                print(e)
                return Response({'error': _('Failed to send SMS message to TCU. Please try again in a moment.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            car.command_type = command_type
            car.command_id = randint(10000, 99999)
            car.command_requested = True
            car.command_result = -1
            car.command_request_time = timezone.now()
            car.save()
            return Response({
                'message': f"Command '{dict(COMMAND_TYPES)[command_type]}' requested successfully",
                'car': CarSerializer(car).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid command type'}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({'error': 'Command type must be an integer'}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):

    @swagger_auto_schema(tags=['token'], request_body=JWTTokenObtainPairSerializer())
    def post(self, request, *args, **kwargs):
        # Call the parent class's post method to get the token response
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Extract token data
            refresh_token_str = response.data.get('refresh')
            access_token = response.data.get('access')

            # Create RefreshToken instance to extract jti
            refresh_token = RefreshToken(refresh_token_str)
            jti = refresh_token['jti']  # Extract the jti from the token

            # Get user from validated serializer
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            user = serializer.user

            # Extract device and other info from request headers or body
            device_type = request.data.get('device_type', '') or request.headers.get('X-Device-Type', '')
            device_os = request.data.get('device_os', '') or request.headers.get('X-Device-OS', '')
            app_version = request.data.get('app_version', '') or request.headers.get('X-App-Version', '')
            push_notification_key = request.data.get('push_notification_key', '')
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            # Save token metadata
            TokenMetadata.objects.create(
                user=user,
                token=jti,
                device_type=device_type,
                device_os=device_os,
                app_version=app_version,
                push_notification_key=push_notification_key,
                ip_address=ip_address,
                user_agent=user_agent
            )

            # Return response with tokens
            return Response({
                'refresh': refresh_token_str,
                'access': access_token,
                'user_id': user.id,
                'username': user.username
            }, status=status.HTTP_200_OK)

        return response