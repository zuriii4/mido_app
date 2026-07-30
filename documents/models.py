from django.db import models

from core.models import BaseModel


class Document(BaseModel):
    document_number = models.CharField(max_length=100, unique=True, db_index=True)
    title = models.CharField(max_length=250)  # nazov aktualnej verzie

    required_bu = models.ForeignKey(
        'users.BusinessUnit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    required_pc = models.ForeignKey(
        'users.ProfessionCategory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    # source: acLibPlatne list item
    ac_dokument_id = models.CharField(max_length=100, db_index=True, blank=True, default='')
    ac_master_id = models.CharField(max_length=100, blank=True, default='')
    content_type_name = models.CharField(max_length=150, blank=True, default='')
    effective_date = models.DateField(null=True, blank=True)
    sp_state = models.CharField(max_length=50, blank=True, default='')
    note = models.TextField(blank=True, default='')
    full_path = models.CharField(max_length=500, blank=True, default='')
    sp_link = models.URLField(max_length=500, blank=True, default='')
    sp_modified_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.document_number} · {self.title}" if self.document_number else self.title

    @property
    def current_version(self):
        return self.versions.filter(is_current=True).first()


class DocumentVersion(BaseModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    # Verzia dokumentu (acColVerzia): '-' (prve vydanie), potom 'A', 'B', 'C', ...
    version_label = models.CharField(max_length=10, default='-')
    title = models.CharField(max_length=250, blank=True, default='')  # nazov v tejto verzii
    file_path = models.FileField(upload_to='documents/')
    is_current = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)

    # SharePoint sync identity/metadata pre tuto verziu (= jedna list-item polozka)
    sharepoint_id = models.IntegerField(unique=True, null=True, blank=True)
    etag = models.CharField(max_length=150, blank=True, default='')
    sp_ui_version = models.CharField(max_length=20, blank=True, default='')  # _UIVersionString ("20.0")
    effective_date = models.DateField(null=True, blank=True)
    sp_modified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['version_label']
        unique_together = ('document', 'version_label')

    def __str__(self):
        return f"{self.document.document_number} v{self.version_label}"


class Attachment(BaseModel):
    document_version = models.ForeignKey(
        DocumentVersion,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file_path = models.FileField(upload_to='attachments/')
    file_name = models.CharField(max_length=255)

    # SharePoint sync identity/metadata (source: acLibPrilohy drive folder = ac_dokument_id)
    sp_item_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    etag = models.CharField(max_length=150, blank=True, default='')
    server_relative_url = models.CharField(max_length=500, blank=True, default='')
    file_size = models.BigIntegerField(null=True, blank=True)
    sp_modified_at = models.DateTimeField(null=True, blank=True)
    # True ak je file_path PDF snapshot skonvertovany zo zdrojoveho formatu (docx/xlsx/doc/...),
    # False ak SharePoint konverziu nepodporoval (napr. json, zip) a je ulozeny original.
    converted_to_pdf = models.BooleanField(default=False)

    def __str__(self):
        return self.file_name



class DocumentVisibilityRule(BaseModel):
    RULE_ALL = 'ALL'
    RULE_BUSINESS_UNIT = 'BUSINESS_UNIT'
    RULE_PROFESSION_CATEGORY = 'PROFESSION_CATEGORY'
    RULE_BOTH = 'BOTH'
    RULE_USER_EXPLICIT = 'USER_EXPLICIT'

    RULE_TYPES = [
        (RULE_ALL, 'All users'),
        (RULE_BUSINESS_UNIT, 'Business unit'),
        (RULE_PROFESSION_CATEGORY, 'Profession category'),
        (RULE_BOTH, 'Business unit AND profession category'),
        (RULE_USER_EXPLICIT, 'Explicit user'),
    ]

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='visibility_rules',
    )
    rule_type = models.CharField(max_length=30, choices=RULE_TYPES)

    business_unit = models.ForeignKey(
        'users.BusinessUnit',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    profession_category = models.ForeignKey(
        'users.ProfessionCategory',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='explicit_document_rules',
    )

    is_exclusion = models.BooleanField(default=False)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        prefix = "EXCLUDE" if self.is_exclusion else "INCLUDE"
        return f"{prefix} · {self.document.title} · {self.rule_type}"