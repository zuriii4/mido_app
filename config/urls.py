from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/signatures/', include('signatures.urls')),
    path('api/auth/', include('rfid_auth.urls')),

    # OpenAPI schema + interaktivna dokumentacia (pre frontend)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

# POZOR: media (PDF dokumentov) sa ZAMERNE neservuju cez Django static handler -
# obchadzalo by to viditelnost. Subory sa streamuju len cez autentifikovane API
# endpointy (documents/views.py: DocumentVersionFileView, AttachmentFileView).
