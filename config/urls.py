from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('kiosk/', include('kiosk.urls')),
    path('api/users/', include('users.urls')),
    path('api/documents/', include('documents.urls')),
    path('api/signatures/', include('signatures.urls')),
    path('api/auth/', include('rfid_auth.urls')),
    path('api/notifications/', include('notifications.urls')),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]