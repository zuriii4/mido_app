from django.urls import path

from signatures.views import (
    DocumentSignaturesReportView,
    MySignaturesView,
    SignView,
    UnsignedReportView,
)

urlpatterns = [
    path('sign/', SignView.as_view(), name='signature-sign'),
    path('mine/', MySignaturesView.as_view(), name='signature-mine'),
    path('reports/document/<uuid:pk>/', DocumentSignaturesReportView.as_view(), name='signature-report-document'),
    path('reports/unsigned/', UnsignedReportView.as_view(), name='signature-report-unsigned'),
]
