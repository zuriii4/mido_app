from django.urls import path

from notifications.views import (
    NotificationsListView,
    UnreadNotificationsListView,
    MarkAsReadView,
)

urlpatterns = [
    path('', NotificationsListView.as_view(), name='notifications-list'),
    path('unread/', UnreadNotificationsListView.as_view(), name='notifications-unread-list'),
    path('mark-as-read/<uuid:pk>/', MarkAsReadView.as_view(), name='mark-as-read'),
]
