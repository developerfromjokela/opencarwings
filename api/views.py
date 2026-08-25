import logging

import django
from dateutil import parser
from dateutil.parser import ParserError
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, permissions
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException
from rest_framework.generics import get_object_or_404, RetrieveAPIView, UpdateAPIView, DestroyAPIView, CreateAPIView, \
    ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from api.models import TokenMetadata
from api.serializers import JWTTokenObtainPairSerializer, TokenMetadataUpdateSerializer, TokenMetadataSerializer, \
    JWTTokenLoginSerializer, PinChangeSerializer, AccountDetailSerializer, APIErrorSerializer
from db.models import Car, AlertHistory, COMMAND_TYPES, CRMDistanceRecord, SENSITIVE_COMMANDS
from tculink.coordinators import TCUCoordinatorError, CommandArgumentError, SMSProviderError
from tculink.coordinators.stub import send_command_using_provider
from ui.serializers import CarSerializer, CarSerializerList, AlertHistorySerializer, \
    CommandResponseSerializer, CommandErrorSerializer, CarUpdatingSerializer, CRMDistanceRecordSerializer, \
    CommandTimerSettingSerializer, AlertHistoryFullSerializer

logger = logging.getLogger("ficosa")


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
    request_body=CarUpdatingSerializer(),
    responses={status.HTTP_200_OK: CarSerializer()}
))
@method_decorator(name='patch', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CarUpdatingSerializer(),
    responses={status.HTTP_200_OK: CarSerializer()}
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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = CarUpdatingSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(CarSerializer(instance).data)



@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['cars'],
    responses={status.HTTP_200_OK: CommandTimerSettingSerializer(many=True)}
))
@method_decorator(name='post', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CommandTimerSettingSerializer(),
    responses={status.HTTP_200_OK: CommandTimerSettingSerializer()}
))
class CommandTimerApiView(ListAPIView, CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommandTimerSettingSerializer

    def perform_create(self, serializer):
        car_vin = self.kwargs['vin']
        car = Car.objects.get(vin=car_vin)
        if car.timer_commands.count() > 5:
            raise APIException(_("Too many timer commands, please delete one and try again"), 400)
        serializer.save()
        car.timer_commands.add(serializer.data['id'])
        car.save()


    def get_queryset(self):
        car_vin = self.kwargs['vin']
        try:
            car_timers = Car.objects.get(vin=car_vin, owner=self.request.user).timer_commands.all()
        except Car.DoesNotExist:
            car_timers = []
        return car_timers


@method_decorator(name='get', decorator=swagger_auto_schema(
    tags=['cars'],
    responses={status.HTTP_200_OK: CommandTimerSettingSerializer()}
))
@method_decorator(name='put', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CommandTimerSettingSerializer(),
    responses={status.HTTP_200_OK: CommandTimerSettingSerializer()}
))
@method_decorator(name='patch', decorator=swagger_auto_schema(
    tags=['cars'],
    request_body=CommandTimerSettingSerializer(),
    responses={status.HTTP_200_OK: CommandTimerSettingSerializer()}
))
@method_decorator(name='delete', decorator=swagger_auto_schema(
    tags=['cars'],
    responses={status.HTTP_204_NO_CONTENT: "Success"}
))
class CommandTimerRetrieveApiView(RetrieveAPIView, UpdateAPIView, DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CommandTimerSettingSerializer
    lookup_field = 'id'

    def get_queryset(self):
        car_vin = self.kwargs['vin']
        try:
            car_timers = Car.objects.get(vin=car_vin, owner=self.request.user).timer_commands.all()
        except Car.DoesNotExist:
            car_timers = []
        return car_timers

    def perform_update(self, serializer):
        serializer.validated_data['last_command_execution'] = None
        serializer.save()



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

        jti = refresh_token.get('orig_jti', None) or refresh_token["jti"]

        # Verify the token belongs to the authenticated user by checking TokenMetadata
        try:
            metadata = TokenMetadata.objects.get(token=jti, user=request.user)
        except ObjectDoesNotExist:
            return Response({"error": "Token metadata not found or does not belong to user"}, status=status.HTTP_404_NOT_FOUND)

        device_type = serializer.validated_data.get('device_type', '') or request.headers.get('X-Device-Type', '')
        device_os = serializer.validated_data.get('device_os', '') or request.headers.get('X-Device-OS', '')
        app_version = serializer.validated_data.get('app_version', '') or request.headers.get('X-App-Version', '')
        push_notification_key = serializer.validated_data.get('push_notification_key', '')
        lang = django.utils.translation.get_language()

        metadata.device_type = device_type
        metadata.lang = lang
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
        jti = refresh_token.get('orig_jti', None) or refresh_token["jti"]

        # Verify the token belongs to the authenticated user by checking TokenMetadata
        try:
            metadata = TokenMetadata.objects.get(token=jti, user=request.user)
        except ObjectDoesNotExist:
            pass

        # Blacklist the token
        try:
            outstanding_token = OutstandingToken.objects.get(jti=refresh_token["jti"])
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
        200: AlertHistoryFullSerializer(many=True),
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


@api_view(['GET'])
def probe_location_hist(request, vin):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    car = get_object_or_404(Car, vin=vin, owner=request.user)

    start_date = request.query_params.get('start')
    end_date = request.query_params.get('end')

    alerts = CRMDistanceRecord.objects.filter(car=car).order_by('-timestamp')
    if start_date and end_date:
        try:
            start = parser.parse(start_date)
            end = parser.parse(end_date)

            if (end - start).days > 34:
                return Response(
                    {'error': 'Date range cannot exceed 34 days'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            alerts = alerts.filter(timestamp__range=[start, end])
        except ParserError:
            return Response(
                {'error': 'Invalid date format'},
                status=status.HTTP_400_BAD_REQUEST
            )
    elif start_date or end_date:
        return Response(
            {'error': 'Both start and end dates are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    else:
        alerts = alerts[:25]

    serializer = CRMDistanceRecordSerializer(alerts, many=True)
    return Response(serializer.data)

@swagger_auto_schema(
    operation_description="Get basic account details",
    tags=['account'],
    method='get',
    responses={
        200: AccountDetailSerializer(),
        401: 'Not authorized',
    }
)
@api_view(['GET'])
def account_info(request):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)

    return Response(AccountDetailSerializer(request.user).data, status=status.HTTP_200_OK)

@swagger_auto_schema(
    operation_description="Change command PIN, requires OTP code if 2FA is enabled, or old pin if disabled",
    request_body=PinChangeSerializer(),
    tags=['account'],
    method='post',
    responses={
        200: 'Success',
        403: 'Invalid OTP Code',
        401: 'Not authorized',
        400: 'Bad Request',
    }
)
@api_view(['POST'])
def change_command_pin(request):
    if not request.user.is_authenticated:
        return Response(status=status.HTTP_401_UNAUTHORIZED)
    serializer = PinChangeSerializer(data=request.data)
    serializer.fields["otp_code"].required = request.user.is_2fa_enabled()
    serializer.fields["old_pin"].required = request.user.is_command_pin_set() and not request.user.is_2fa_enabled()

    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    if (request.user.is_command_pin_set() and not request.user.is_2fa_enabled()
            and not request.user.verify_command_pin(serializer.data['old_pin'])):
        return Response({'error': _("Invalid PIN, please try again")}, status=status.HTTP_403_FORBIDDEN)

    if request.user.is_2fa_enabled() and not request.user.verify_otp(serializer.data['otp_code']):
        return Response({'error': _("Invalid OTP, please try again")}, status=status.HTTP_403_FORBIDDEN)

    request.user.set_command_pin(serializer.data['new_pin'])
    request.user.save()

    return Response({'success': True}, status=status.HTTP_200_OK)


@swagger_auto_schema(
    operation_description="Send a command to your vehicle",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            'command_type': openapi.Schema(type=openapi.TYPE_NUMBER, title="Command type", enum=COMMAND_TYPES),
            'command_payload': openapi.Schema(type=openapi.TYPE_OBJECT, default=None),
            'command_pin': openapi.Schema(type=openapi.TYPE_STRING, default=None, title=f"PIN code for command types {SENSITIVE_COMMANDS}"),
        },
        required=['vin', 'command_type']
    ),
    tags=['cars'],
    method='post',
    responses={
        200: CommandResponseSerializer(),
        403: 'Command PIN not set up or invalid',
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
    command_payload = request.data.get('command_payload', None)
    command_pin = request.data.get('command_pin', None)

    try:
        command_type = int(command_type)
        if command_type in dict(COMMAND_TYPES):
            if command_type in SENSITIVE_COMMANDS:
                if not request.user.is_command_pin_set() and hasattr(django.conf.settings, 'PIN_ENFORCE') and django.conf.settings.PIN_ENFORCE:
                    return Response({'error': _("Command PIN is not set up, please set up and try again")}, status=status.HTTP_403_FORBIDDEN)
                if request.user.is_command_pin_set() and (command_pin is None or not request.user.verify_command_pin(command_pin)):
                    return Response({'error': _("Invalid PIN, please try again")}, status=status.HTTP_403_FORBIDDEN)
            try:
                car = send_command_using_provider(command_type, command_payload, car)
            except CommandArgumentError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except SMSProviderError as e:
                logger.exception(e)
                return Response({'error': e.error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except TCUCoordinatorError as e:
                logger.exception(e)
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            except Exception as e:
                logger.exception(e)
                return Response({'error': _('Failed to send SMS message to TCU. Please try again in a moment.')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({
                'message': f"Command '{dict(COMMAND_TYPES)[command_type]}' requested successfully",
                'car': CarSerializer(car).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid command type'}, status=status.HTTP_400_BAD_REQUEST)
    except (ValueError, TypeError):
        return Response({'error': 'Command type must be an integer'}, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = JWTTokenObtainPairSerializer
    @swagger_auto_schema(tags=['token'], request_body=JWTTokenObtainPairSerializer(), responses={
        200: JWTTokenLoginSerializer(),
        401: APIErrorSerializer()
    })
    def post(self, request, *args, **kwargs):
        # Call the parent class's post method to get the token response
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            # Extract token data
            refresh_token_str = response.data.get('refresh')
            access_token = response.data.get('access')

            # Create RefreshToken instance to extract jti
            refresh_token = RefreshToken(refresh_token_str)
            jti = refresh_token.get('orig_jti', None) or refresh_token["jti"]

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
            lang = django.utils.translation.get_language()

            # Save token metadata
            TokenMetadata.objects.create(
                user=user,
                token=jti,
                lang=lang,
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