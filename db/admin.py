from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    TCUConfiguration,
    LocationInfo,
    EVInfo,
    AlertHistory,
    Car, User, SendToCarLocation, CRMLatest, CRMLifetime, CRMExcessiveAirconRecord, CRMExcessiveIdlingRecord,
    CRMMonthlyRecord, CRMMSNRecord, CRMChargeRecord, CRMChargeHistoryRecord, CRMABSHistoryRecord, CRMTroubleRecord,
    CRMTripRecord, RoutePlan, DOTFile, CRMDistanceRecord, ProbeConfig
)


@admin.register(TCUConfiguration)
class TCUConfigurationAdmin(admin.ModelAdmin):
    list_display = ('id', 'dial_code', 'apn', 'server_url', 'last_updated')
    list_filter = ('connection_type', 'last_updated')
    search_fields = ('dial_code', 'apn', 'server_url')


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
    raw_id_fields = ('tcu_configuration', 'location', 'ev_info')

    # Custom methods to display choice field values
    def command_type_display(self, obj):
        return obj.get_command_type_display()

    command_type_display.short_description = 'Command Type'

    def command_result_display(self, obj):
        return obj.get_command_result_display()

    command_result_display.short_description = 'Command Result'

    fieldsets = (
        ('Vehicle Info', {
            'fields': ('vin', 'sms_config', 'vehicle_code1', 'vehicle_code2',
                       'vehicle_code3', 'vehicle_code4', 'nickname', 'owner', 'odometer', 'signal_level', 'carrier', 'map_version', 'navi_version')
        }),
        ('TCU Info', {
            'fields': ('tcu_model', 'tcu_serial', 'iccid', 'tcu_ver',
                       'tcu_user', 'tcu_pass', 'last_connection', 'disable_auth')
        }),
        ('Related Objects', {
            'fields': ('tcu_configuration', 'location', 'ev_info', 'send_to_car_location', 'route_plans')
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
                    'email_notifications'
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