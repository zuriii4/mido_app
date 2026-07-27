from django.contrib import admin

from users.models import BusinessUnit, ProfessionCategory, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'firstname', 'lastname', 'rfid_uid',
                    'business_unit', 'profession_code', 'is_active', 'is_staff')
    list_filter = ('is_active', 'is_staff', 'business_unit', 'profession_code')
    search_fields = ('username', 'firstname', 'lastname', 'rfid_uid', 'external_id')
    readonly_fields = ('last_synced_at', 'last_login')
    autocomplete_fields = ('business_unit', 'profession_code')


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ('code',)
    search_fields = ('code',)


@admin.register(ProfessionCategory)
class ProfessionCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
