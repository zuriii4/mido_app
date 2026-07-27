from django.conf import settings
from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from drf_spectacular.utils import extend_schema

from documents.services import get_unsigned_documents
from rfid_auth.authentication import KioskDeviceAuthentication, RfidSessionAuthentication
from rfid_auth.models import RfidSession
from rfid_auth.permissions import IsKioskDevice
from rfid_auth.serializers import RfidLoginResponseSerializer, RfidLoginSerializer
from users.serializers import UserSerializer


@extend_schema(
    request=RfidLoginSerializer,
    responses={201: RfidLoginResponseSerializer},
)
class RfidLoginView(APIView):
    """Priloziu kartu na kiosku -> vznikne casovo obmedzena session (Bearer token)."""

    authentication_classes = [KioskDeviceAuthentication]
    permission_classes = [IsKioskDevice]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'rfid_login'  # rate v settings DEFAULT_THROTTLE_RATES

    def post(self, request):
        serializer = RfidLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rfid_uid = serializer.validated_data['rfid_uid']

        user = authenticate(request, rfid_uid=rfid_uid)
        if user is None:
            return Response(
                {'detail': 'Neznama alebo neaktivna RFID karta.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # jedna aktivna session na pouzivatela - stare (este platne) revokuj,
        # aby zabudnute prihlasenie na inom kiosku neostalo otvorene
        now = timezone.now()
        RfidSession.objects.filter(
            user=user, revoked_at__isnull=True, expires_at__gt=now
        ).update(revoked_at=now)

        session = RfidSession.objects.create(
            user=user,
            device=request.auth,
            expires_at=timezone.now() + settings.RFID_SESSION_TTL,
        )
        return Response(
            {
                'token': session.token,
                'expires_at': session.expires_at,
                'user': UserSerializer(user).data,
                'unsigned_count': get_unsigned_documents(user).count(),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(request=None, responses={204: None})
class RfidLogoutView(APIView):
    authentication_classes = [RfidSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session = request.auth
        session.revoked_at = timezone.now()
        session.save(update_fields=['revoked_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
