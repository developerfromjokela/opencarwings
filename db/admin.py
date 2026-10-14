import smtplib

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.views import redirect_to_login
from django.core.mail import send_mail
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _, gettext_lazy

from .models import (
    TCUConfiguration,
    LocationInfo,
    EVInfo,
    AlertHistory,
    Car, User, SendToCarLocation, CRMLatest, CRMLifetime, CRMExcessiveAirconRecord, CRMExcessiveIdlingRecord,
    CRMMonthlyRecord, CRMMSNRecord, CRMChargeRecord, CRMChargeHistoryRecord, CRMABSHistoryRecord, CRMTroubleRecord,
    CRMTripRecord, RoutePlan, DOTFile, CRMDistanceRecord, ProbeConfig, CommandTimerSetting, VehicleHealthInfo,
    CarTransferRequest
)


def login(self, request, extra_context=None):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url='signin')
    if self.has_permission(request):
        index_path = reverse('admin:index', current_app=self.name)
        return redirect(index_path)
    else:
        return redirect('/')

admin.site.__class__.login = login

@admin.register(TCUConfiguration)
class TCUConfigurationAdmin(admin.ModelAdmin):
    list_display = ('id', 'dial_code', 'apn', 'server_url', 'last_updated')
    list_filter = ('connection_type', 'last_updated')
    search_fields = ('dial_code', 'apn', 'server_url')

@admin.register(VehicleHealthInfo)
class VehicleHealthAdmin(admin.ModelAdmin):
    list_display = ('id', 'tpms_light', 'maintenance_alert', 'mileage', 'last_updated')
    list_filter = ('maintenance_alert', 'tpms_light')

@admin.register(LocationInfo)
class LocationInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'lat', 'lon', 'home', 'last_updated')
    list_filter = ('home', 'last_updated')
    search_fields = ('lat', 'lon')

@admin.register(SendToCarLocation)
class SendToCarLocationAdmin(admin.ModelAdmin):
    list_display = ('id', 'lat', 'lon', 'name', 'created_at')
    list_filter = ('name', 'created_at')
    search_fields = ('lat', 'lon', 'name')

@admin.register(RoutePlan)
class RoutePlanAdmin(admin.ModelAdmin):
    list_display = ('id',  'created_at', 'name')
    list_filter = ('name',)
    search_fields = ('name',)


@admin.register(EVInfo)
class EVInfoAdmin(admin.ModelAdmin):
    list_display = ('id', 'range_acon', 'range_acoff', 'plugged_in', 'charging', 'ac_status', 'last_updated')
    list_filter = ('plugged_in', 'charging', 'ac_status', 'last_updated')
    search_fields = ('range_acon', 'range_acoff')


@admin.register(AlertHistory)
class AlertHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_type_display', 'timestamp', 'command_id', 'car')
    list_filter = ('type', 'timestamp')
    search_fields = ('additional_data', 'car__vin')
    raw_id_fields = ('car',)  # Improves performance for ForeignKey field

@admin.register(CommandTimerSetting)
class CommandTimerSettingAdmin(admin.ModelAdmin):
    list_display = ('id', 'command_type', 'timer_type')

@admin.register(CarTransferRequest)
class CarTransferRequestAdmin(admin.ModelAdmin):
    list_display = ('car', 'recipient_email', 'request_created', 'expiration_time', 'claimed_by', 'claimed_at')
    list_filter = ('claimed_at', 'request_created')
    search_fields = ('car__vin', 'recipient_email')
    raw_id_fields = ('car',)  # Improves performance for ForeignKey field
    readonly_fields = ('transfer_link', 'request_created', 'previous_owner', 'claimed_by', 'claimed_at')
    fields = ('car', 'recipient_email', 'keep_history', 'expiration_time') + readonly_fields

    def get_readonly_fields(self, request, obj=None):
        # The link was already emailed for this car and address
        return self.readonly_fields + (('car', 'recipient_email') if obj else ())

    @admin.display(description=gettext_lazy('Transfer link'))
    def transfer_link(self, obj):
        if not obj.pk:
            return '-'
        return format_html('<a href="{0}">{0}</a>', obj.get_absolute_url())

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if change:
            return
        link = request.build_absolute_uri(obj.get_absolute_url())
        body = render_to_string('emails/car_transfer.txt', {
            'from_user': obj.car.owner.username, 'car': obj.car, 'email': obj.recipient_email,
            'link': link, 'expires': obj.expiration_time,
        })
        try:
            subject = _('%(user)s is transferring a car to you') % {'user': obj.car.owner.username}
            send_mail(f'{subject} - OpenCARWINGS', body,
                      settings.DEFAULT_FROM_EMAIL, [obj.recipient_email])
            self.message_user(request, _('Transfer link sent to %(email)s.') % {'email': obj.recipient_email})
        except (smtplib.SMTPException, OSError):
            self.message_user(request, _('The email could not be sent. Send this link to %(email)s yourself: %(link)s')
                              % {'email': obj.recipient_email, 'link': link}, messages.WARNING)

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = (
        'vin', 'iccid', 'nickname', 'tcu_model', 'tcu_serial',
        'last_connection', 'command_type_display', 'command_result_display'
    )
    list_filter = (
        'command_type', 'command_result', 'command_requested',
        'last_connection'
    )
    search_fields = ('vin', 'tcu_serial', 'tcu_model', 'iccid', 'nickname')
    raw_id_fields = ('tcu_configuration', 'location', 'ev_info', 'veh_health')

    # Custom methods to display choice field values
    def command_type_display(self, obj):
        return obj.get_command_type_display()

    command_type_display.short_description = 'Command Type'

    def command_result_display(self, obj):
        return obj.get_command_result_display()

    command_result_display.short_description = 'Command Result'

    fieldsets = (
        ('Vehicle Info', {
            'fields': ('tcu_type', 'vin', 'sms_config', 'hmac_key', 'vehicle_code1', 'vehicle_code2',
                       'vehicle_code3', 'vehicle_code4', 'nickname', 'owner', 'odometer', 'signal_level', 'carrier', 'map_version', 'navi_version')
        }),
        ('Timer', {
            'fields': ('timer_commands',)
        }),
        ('TCU Info', {
            'fields': ('tcu_model', 'tcu_serial', 'iccid', 'tcu_ver',
                       'tcu_user', 'tcu_pass', 'last_connection', 'disable_auth')
        }),
        ('Related Objects', {
            'fields': ('tcu_configuration', 'location', 'ev_info', 'send_to_car_location', 'route_plans', 'veh_health')
        }),
        ('Command Info', {
            'fields': ('command_id', 'command_result', 'command_requested',
                       'command_payload', 'command_type', 'command_request_time')
        }),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets+ (
        (
            'CarWings fields',
            {
                'fields': (
                    'tcu_pass_hash',
                    'email_notifications',
                    'cmd_pin_hash'
                ),
            },
        ),
    )

# PRB
@admin.register(ProbeConfig)
class ProbeConfigAdmin(admin.ModelAdmin):
    list_display = ('car', 'config_id')

@admin.register(CRMLatest)
class CRMLatestAdmin(admin.ModelAdmin):
    list_display = ('car', 'odometer', 'last_updated')

@admin.register(CRMLifetime)
class CRMLifetimeAdmin(admin.ModelAdmin):
    list_display = ('car', 'last_updated')

@admin.register(CRMExcessiveAirconRecord)
class CRMExcessiveAirconRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start', 'consumption')

@admin.register(CRMExcessiveIdlingRecord)
class CRMExcessiveIdlingRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start', 'duration')

@admin.register(CRMMonthlyRecord)
class CRMMonthlyRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start', 'end', 'trip_count')

@admin.register(CRMMSNRecord)
class CRMMSNRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'timestamp')

@admin.register(CRMDistanceRecord)
class CRMDistanceRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'timestamp')

@admin.register(CRMChargeRecord)
class CRMChargeRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start_time', 'end_time', 'charge_type')

@admin.register(CRMChargeHistoryRecord)
class CRMChargeHistoryRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start_time', 'end_time', 'charging_type')

@admin.register(CRMABSHistoryRecord)
class CRMABSHistoryRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'timestamp')

@admin.register(CRMTroubleRecord)
class CRMTroubleRecordAdmin(admin.ModelAdmin):
    list_display = ('car',)

@admin.register(CRMTripRecord)
class CRMTripRecordAdmin(admin.ModelAdmin):
    list_display = ('car', 'start_ts', 'end_ts', 'distance')

@admin.register(DOTFile)
class DOTFileAdmin(admin.ModelAdmin):
    list_display = ('car', 'upload_ts', 'capture_ts')