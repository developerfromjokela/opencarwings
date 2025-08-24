from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    TCUConfiguration,
    LocationInfo,
    EVInfo,
    AlertHistory,
    Car, User, SendToCarLocation
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
    list_display = ('id', 'lat', 'lon', 'name')
    list_filter = ('name',)
    search_fields = ('lat', 'lon', 'name')


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
                       'vehicle_code3', 'vehicle_code4', 'nickname', 'owner')
        }),
        ('TCU Info', {
            'fields': ('tcu_model', 'tcu_serial', 'iccid', 'tcu_ver',
                       'tcu_user', 'tcu_pass', 'last_connection', 'disable_auth')
        }),
        ('Related Objects', {
            'fields': ('tcu_configuration', 'location', 'ev_info', 'send_to_car_location')
        }),
        ('Command Info', {
            'fields': ('command_id', 'command_result', 'command_requested',
                       'command_payload', 'command_type', 'command_request_time')
        }),
    )

# If you prefer a simpler registration without customizations, you could just use:
# admin.site.register(TCUConfiguration)
# admin.site.register(LocationInfo)
# admin.site.register(EVInfo)
# admin.site.register(AlertHistory)
# admin.site.register(Car)
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