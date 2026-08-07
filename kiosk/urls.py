from django.urls import path

from . import views

app_name = 'kiosk'

urlpatterns = [
    path('', views.KioskView.as_view(), name='home'),
    path('device-setup/', views.DeviceSetupView.as_view(), name='device-setup'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('document/<uuid:pk>/', views.DocumentDetailView.as_view(), name='document'),
    path('notification/<uuid:notification_id>/read/', views.MarkAsReadNotificationView.as_view(), name='mark-notification-as-read'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
]
