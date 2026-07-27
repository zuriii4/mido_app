from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rfid_auth.authentication import RfidSessionAuthentication
from users.models import BusinessUnit, ProfessionCategory, User
from users.serializers import (
    BusinessUnitSerializer,
    ProfessionCategorySerializer,
    UserAdminSerializer,
    UserSerializer,
)


class MeView(APIView):
    """GET /api/users/me — profil prihlaseneho pouzivatela."""

    authentication_classes = [RfidSessionAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListCreateView(ListCreateAPIView):
    """GET/POST /api/users — staff sprava pouzivatelov.
    Filtre: ?is_active=&is_staff=&business_unit=<kod>; search: ?search=<meno/username/rfid>."""

    queryset = User.objects.select_related('business_unit', 'profession_code').order_by(
        'lastname', 'firstname'
    )
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = {
        'is_active': ['exact'],
        'is_staff': ['exact'],
        'business_unit__code': ['exact'],
    }
    search_fields = ['username', 'firstname', 'lastname', 'rfid_uid', 'external_id']


class UserDetailView(RetrieveUpdateAPIView):
    """GET/PATCH /api/users/{id} — detail a uprava pouzivatela (staff).
    Cez PATCH sa priraduje/meni RFID karta (rfid_uid) aj is_active."""

    queryset = User.objects.select_related('business_unit', 'profession_code')
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'head', 'options']  # bez PUT (nechceme plnu vymenu)


class BusinessUnitListView(ListAPIView):
    """GET /api/users/business-units — ciselnik prevadzok (pre vyber pri sprave pouzivatelov)."""

    queryset = BusinessUnit.objects.all()
    serializer_class = BusinessUnitSerializer


class ProfessionCategoryListView(ListAPIView):
    """GET /api/users/profession-categories — ciselnik profesnych kategorii."""

    queryset = ProfessionCategory.objects.all().order_by('name')
    serializer_class = ProfessionCategorySerializer