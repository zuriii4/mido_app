from django.urls import path

from documents.views import (
    AttachmentFileView,
    DocumentDetailView,
    DocumentListView,
    DocumentVersionFileView,
    DocumentVersionsView,
)

urlpatterns = [
    path('', DocumentListView.as_view(), name='document-list'),
    path('versions/<uuid:pk>/file/', DocumentVersionFileView.as_view(), name='document-version-file'),
    path('attachments/<uuid:pk>/file/', AttachmentFileView.as_view(), name='attachment-file'),
    path('<uuid:pk>/', DocumentDetailView.as_view(), name='document-detail'),
    path('<uuid:pk>/versions/', DocumentVersionsView.as_view(), name='document-versions'),
]
