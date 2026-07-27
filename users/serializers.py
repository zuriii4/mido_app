from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from users.models import BusinessUnit, ProfessionCategory, User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    business_unit = serializers.CharField(source='business_unit.code', read_only=True, default=None)
    profession_category = serializers.CharField(source='profession_code.name', read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'firstname', 'lastname', 'full_name',
            'rfid_uid', 'business_unit', 'profession_category', 'is_active',
        ]
        read_only_fields = fields


class UserAdminSerializer(serializers.ModelSerializer):
    """Zapisovatelny serializer pre staff spravu pouzivatelov (create/update).
    business_unit a profession_category sa referencuju cez ludsky citatelny kod/nazov."""

    full_name = serializers.CharField(read_only=True)
    rfid_uid = serializers.CharField(
        max_length=60, required=False, allow_null=True, allow_blank=True,
        validators=[UniqueValidator(queryset=User.objects.all())],
    )
    business_unit = serializers.SlugRelatedField(
        slug_field='code', queryset=BusinessUnit.objects.all(),
        allow_null=True, required=False,
    )
    profession_category = serializers.SlugRelatedField(
        source='profession_code', slug_field='name',
        queryset=ProfessionCategory.objects.all(),
        allow_null=True, required=False,
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'firstname', 'lastname', 'full_name',
            'rfid_uid', 'business_unit', 'profession_category',
            'external_id', 'is_active', 'is_staff', 'last_synced_at',
        ]
        read_only_fields = ['id', 'full_name', 'last_synced_at']

    def validate_rfid_uid(self, value):
        # prazdny retazec by kolidoval v unique indexe (viac "" nie je povolenych);
        # ziadna karta = NULL
        return value or None


class BusinessUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessUnit
        fields = ['id', 'code']


class ProfessionCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProfessionCategory
        fields = ['id', 'name']
