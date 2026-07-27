from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from core.models import BaseModel


class BusinessUnit(BaseModel):
    code = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code


class ProfessionCategory(BaseModel):
    name = models.CharField(max_length=50, unique=True)
    profession_code = models.JSONField(default=dict)

    class Meta:
        verbose_name_plural = "Profession categories"


    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Users must have a username')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password, **extra_fields):
        if not username:
            raise ValueError('Users must have a username')
        super_user = self.create_user(username, password, **extra_fields)
        super_user.is_staff = True
        super_user.is_superuser = True
        super_user.set_password(password)
        super_user.save(using=self._db)
        return super_user


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    username = models.CharField(max_length=150, unique=True)
    firstname = models.CharField(max_length=50)
    lastname = models.CharField(max_length=50)
    rfid_uid = models.CharField(max_length=60, unique=True, null=True)
    profession_code = models.ForeignKey(ProfessionCategory, on_delete=models.SET_NULL, null=True, blank=True)
    business_unit = models.ForeignKey(BusinessUnit, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # pristup do admin rozhrania + staff-only reporty
    external_id = models.CharField(max_length=50, unique=True, null=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    def __str__(self):
        return f"{self.rfid_uid} - {self.firstname} {self.lastname}"

    @property
    def full_name(self):
        return f"{self.firstname} {self.lastname}".strip()
