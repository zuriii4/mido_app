from django.contrib import admin

from rfid_auth.models import KioskDevice, RfidSession


@admin.register(KioskDevice)
class KioskDeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active', 'last_seen_at')
    readonly_fields = ('token',)


@admin.register(RfidSession)
class RfidSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device', 'expires_at', 'revoked_at', 'created_at')
    list_filter = ('device',)
    search_fields = ('user__username', 'user__rfid_uid')
    readonly_fields = ('token',)
