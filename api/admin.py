from django.contrib import admin

from api.models import TokenMetadata

# Register your models here.

@admin.register(TokenMetadata)
class TCUConfigurationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'token', 'device_type', 'lang')
    list_filter = ('id', 'user', 'token', 'device_type', 'lang')
