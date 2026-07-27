from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.models import Document, DocumentVersion
from documents.services import get_required_users
from signatures.models import Signature
from signatures.serializers import (
    SignatureReportSerializer,
    SignatureSerializer,
    SignRequestSerializer,
)
from signatures.services import create_signature
from users.serializers import UserSerializer


@extend_schema(
    request=SignRequestSerializer,
    responses={201: SignatureSerializer},
)
class SignView(APIView):
    """POST /api/signatures/sign — podpis potvrdeny opatovnym prilozenim RFID karty."""

    def post(self, request):
        serializer = SignRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        version = DocumentVersion.objects.select_related('document').filter(
            pk=serializer.validated_data['document_version_id']
        ).first()
        if version is None:
            raise Http404

        signature = create_signature(
            user=request.user,
            document_version=version,
            rfid_uid=serializer.validated_data['rfid_uid'],
            ip_address=request.META.get('REMOTE_ADDR'),
            device=getattr(request.auth, 'device', None),  # request.auth = RfidSession
        )
        return Response(SignatureSerializer(signature).data, status=status.HTTP_201_CREATED)


class MySignaturesView(ListAPIView):
    """GET /api/signatures/mine — historia podpisov prihlaseneho pouzivatela."""

    serializer_class = SignatureSerializer

    def get_queryset(self):
        return (
            Signature.objects
            .filter(user=self.request.user)
            .select_related('document_version__document')
        )


class DocumentSignaturesReportView(ListAPIView):
    """GET /api/signatures/reports/document/{id}/ — kto podpisal ktoru verziu (staff)."""

    serializer_class = SignatureReportSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not Document.objects.filter(pk=self.kwargs['pk']).exists():
            raise Http404
        return (
            Signature.objects
            .filter(document_version__document_id=self.kwargs['pk'])
            .select_related('user', 'document_version')
        )


class UnsignedReportView(ListAPIView):
    """GET /api/signatures/reports/unsigned/?document_id=&business_unit= —
    kto este nepodpisal aktualnu verziu dokumentu (staff)."""

    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        document_id = self.request.query_params.get('document_id')
        if not document_id:
            raise ValidationError({'document_id': 'Povinny parameter.'})
        document = Document.objects.filter(pk=document_id).first()
        if document is None:
            raise Http404

        users = get_required_users(document)

        business_unit = self.request.query_params.get('business_unit')
        if business_unit:
            users = users.filter(business_unit__code=business_unit)

        current_version = document.current_version
        if current_version is None:
            return users  # bez verzie nemohol podpisat nikto
        signed_user_ids = Signature.objects.filter(
            document_version=current_version
        ).values_list('user_id', flat=True)
        return users.exclude(pk__in=signed_user_ids)
