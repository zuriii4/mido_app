from django.contrib import admin

from documents.models import Attachment, Document, DocumentVersion, DocumentVisibilityRule


class DocumentVersionInline(admin.TabularInline):
    model = DocumentVersion
    extra = 0
    fields = ('version_label', 'title', 'sharepoint_id', 'sp_ui_version', 'is_current', 'file_path', 'published_at')
    readonly_fields = fields


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('document_number', 'title', 'sp_state', 'is_active', 'effective_date', 'last_synced_at')
    list_filter = ('is_active', 'sp_state', 'content_type_name')
    search_fields = ('document_number', 'title', 'ac_dokument_id')
    inlines = [DocumentVersionInline]


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ('document', 'version_label', 'sp_ui_version', 'is_current', 'published_at')
    list_filter = ('is_current',)
    search_fields = ('document__document_number', 'document__title')


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'document_version', 'file_size', 'sp_modified_at')
    search_fields = ('file_name',)


@admin.register(DocumentVisibilityRule)
class DocumentVisibilityRuleAdmin(admin.ModelAdmin):
    list_display = ('document', 'rule_type', 'is_exclusion', 'business_unit',
                    'profession_category', 'user', 'valid_from', 'valid_to')
    list_filter = ('rule_type', 'is_exclusion')
    search_fields = ('document__title',)
    autocomplete_fields = ('document',)
    raw_id_fields = ('user',)