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

class DocumentAssignmentQuerySet(models.QuerySet):
    def active_now(self):
        """Priradenia ucinne v danom okamihu (null hranice = bez obmedzenia)."""
        from django.utils import timezone
        now = timezone.now()
        return self.filter(
            models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now),
            models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=now),
        )


class DocumentAssignment(BaseModel):
    """Priradenie dokumentu cielovej skupine pouzivatelov"""
    TARGET_ALL = 'ALL'
    TARGET_BUSINESS_UNIT = 'BUSINESS_UNIT'
    TARGET_PROFESSION_CATEGORY = 'PROFESSION_CATEGORY'
    TARGET_BOTH = 'BOTH'
    TARGET_USER = 'USER'

    TARGET_TYPES = [
        (TARGET_ALL, 'Všetci používatelia'),
        (TARGET_BUSINESS_UNIT, 'Business unit'),
        (TARGET_PROFESSION_CATEGORY, 'Profession category'),
        (TARGET_BOTH, 'Business unit A profession category'),
        (TARGET_USER, 'Konkrétny používateľ'),
    ]

    document_version = models.ForeignKey(
        'documents.DocumentVersion',
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    target_type = models.CharField(max_length=30, choices=TARGET_TYPES)

    business_units = models.ManyToManyField(
        'users.BusinessUnit',
        blank=True,
        related_name='document_assignments',
    )
    profession_categories = models.ManyToManyField(
        'users.ProfessionCategory',
        blank=True,
        related_name='document_assignments',
    )
    users = models.ManyToManyField(
        'users.User',
        blank=True,
        related_name='document_assignments',
    )

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True, default='')

    objects = DocumentAssignmentQuerySet.as_manager()

    class Meta:
        ordering = ['document_version_id', 'target_type']
        verbose_name = 'Priradenie dokumentu'
        verbose_name_plural = 'Priradenia dokumentov'

    def __str__(self):
        return f"{self.document_version.document.document_number} v{self.document_version.version_label} -> {self.describe_target()}"

    def describe_target(self):
        if self.target_type == self.TARGET_ALL:
            return 'Všetci používatelia'
        parts = []
        if self.target_type in (self.TARGET_BUSINESS_UNIT, self.TARGET_BOTH):
            codes = ', '.join(self.business_units.values_list('code', flat=True))
            parts.append(f'BU {codes}')
        if self.target_type in (self.TARGET_PROFESSION_CATEGORY, self.TARGET_BOTH):
            names = ', '.join(self.profession_categories.values_list('name', flat=True))
            parts.append(f'profesia: {names}')
        if self.target_type == self.TARGET_USER:
            names = ', '.join(self.users.values_list('username', flat=True))
            parts.append(f'používatelia: {names}')
        return ' | '.join(parts) if parts else self.get_target_type_display()

    # ------------------------------------------------------------------
    # Matching logika
    # ------------------------------------------------------------------
    def matching_user_q(self):
        """Q nad User queryset: pouzivatelia, na ktorych sa priradenie vztahuje."""
        if self.target_type == self.TARGET_ALL:
            return models.Q()
        if self.target_type == self.TARGET_BUSINESS_UNIT:
            return models.Q(business_unit__in=self.business_units.all())
        if self.target_type == self.TARGET_PROFESSION_CATEGORY:
            return models.Q(profession_code__in=self.profession_categories.all())
        if self.target_type == self.TARGET_BOTH:
            return (
                models.Q(business_unit__in=self.business_units.all())
                & models.Q(profession_code__in=self.profession_categories.all())
            )
        if self.target_type == self.TARGET_USER:
            return models.Q(pk__in=self.users.all())
        return models.Q(pk__in=[])

    def matches_user(self, user):
        """Kontrola pre jedneho pouzivatela."""
        if self.target_type == self.TARGET_ALL:
            return True
        if self.target_type == self.TARGET_USER:
            return self.users.filter(pk=user.pk).exists()

        bu_ok = pc_ok = True
        if self.target_type in (self.TARGET_BUSINESS_UNIT, self.TARGET_BOTH):
            bu_ok = (
                user.business_unit_id is not None
                and self.business_units.filter(pk=user.business_unit_id).exists()
            )
        if self.target_type in (self.TARGET_PROFESSION_CATEGORY, self.TARGET_BOTH):
            pc_ok = (
                user.profession_code_id is not None
                and self.profession_categories.filter(pk=user.profession_code_id).exists()
            )
        return bu_ok and pc_ok


    # ------------------------------------------------------------------
    # Hromadne dotazy
    # ------------------------------------------------------------------
    @classmethod
    def get_assigned_users(cls, document_version):
        """Vsetci aktivni pouzivatelia, ktorym je dana verzia dokumentu
        priradena (OR cez vsetky aktivne priradenia verzie)."""
        from users.models import User
        combined = models.Q()
        assignments = cls.objects.filter(document_version=document_version).active_now().prefetch_related(
            'business_units', 'profession_categories', 'users')
        for assignment in assignments:
            combined |= assignment.matching_user_q()
        return User.objects.filter(combined, is_active=True).distinct()

    @classmethod
    def get_assigned_versions(cls, user):
        """Aktivne verzie dokumentov priradene danemu pouzivatelovi."""
        ids = set()
        for assignment in cls.objects.active_now().prefetch_related(
                'business_units', 'profession_categories', 'users'):
            if assignment.matches_user(user):
                ids.add(assignment.document_version_id)
        return DocumentVersion.objects.filter(pk__in=ids, document__is_active=True)

class DocumentVersion(BaseModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='versions',
    )
    version_label = models.CharField(max_length=10, default='-')
    title = models.CharField(max_length=250, blank=True, default='')  
    file_path = models.FileField(upload_to='documents/')
    is_current = models.BooleanField(default=True)
    published_at = models.DateTimeField(auto_now_add=True)

    sharepoint_id = models.IntegerField(unique=True, null=True, blank=True)
    etag = models.CharField(max_length=150, blank=True, default='')
    sp_ui_version = models.CharField(max_length=20, blank=True, default='') 
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

    sp_item_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    etag = models.CharField(max_length=150, blank=True, default='')
    server_relative_url = models.CharField(max_length=500, blank=True, default='')
    file_size = models.BigIntegerField(null=True, blank=True)
    sp_modified_at = models.DateTimeField(null=True, blank=True)
    converted_to_pdf = models.BooleanField(default=False)

    def __str__(self):
        return self.file_name
