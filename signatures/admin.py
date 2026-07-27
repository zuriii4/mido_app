from django.contrib import admin

from signatures.models import Signature


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_version', 'signed_at', 'device_id', 'rfid_uid_used')
    list_filter = ('device_id',)
    search_fields = ('user__username', 'user__lastname', 'document_version__document__title')
    readonly_fields = ('user', 'document_version', 'signed_at', 'rfid_uid_used', 'ip_address', 'device_id')

    def has_add_permission(self, request):
        return False  # podpis vznika len cez API s RFID re-tap, nie rucne v admine

    def has_change_permission(self, request, obj=None):
        return False
