from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from documents.models import Attachment, Document, DocumentAssignment, DocumentVersion


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


class DocumentAssignmentForm(forms.ModelForm):
    class Meta:
        model = DocumentAssignment
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        target_type = cleaned_data.get("target_type")

        if target_type == "USER" and not cleaned_data.get("users"):
            raise ValidationError("Pre typ USER vyber aspoň jedného používateľa.")
        if target_type == "BUSINESS_UNIT" and not cleaned_data.get("business_units"):
            raise ValidationError("Pre typ BUSINESS_UNIT vyber aspoň jednu business unit.")
        if target_type == "PROFESSION_CATEGORY" and not cleaned_data.get("profession_categories"):
            raise ValidationError("Pre typ PROFESSION_CATEGORY vyber aspoň jednu kategóriu.")
        if target_type == "BOTH" and (
            not cleaned_data.get("business_units")
            or not cleaned_data.get("profession_categories")
        ):
            raise ValidationError("Pre typ BOTH vyber business unit aj profession category.")

        return cleaned_data


@admin.register(DocumentAssignment)
class DocumentAssignmentAdmin(admin.ModelAdmin):
    form = DocumentAssignmentForm
    list_display = ('document_version', 'target_type', 'describe_target', 'valid_from', 'valid_to')
    list_filter = ('target_type',)
    search_fields = ('document__document_number', 'document__title')
    autocomplete_fields = ('document_version',)
    filter_horizontal = ('business_units', 'profession_categories', 'users')
