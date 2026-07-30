from rest_framework.response import Response
from rest_framework.generics import ListAPIView, UpdateAPIView

from notifications.models import Notification
from notifications.serializers import MarkAsReadSerializer, NotificationSerializer
from notifications.services import get_notifications, get_unread_notifications, mark_notification_as_read


class NotificationsListView(ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return get_notifications(self.request.user) 

class UnreadNotificationsListView(ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return get_unread_notifications(self.request.user)

class MarkAsReadView(UpdateAPIView):
    serializer_class = MarkAsReadSerializer

    def get_queryset(self):
        return get_notifications(self.request.user)


    def update(self, request, *args, **kwargs):
        notification = mark_notification_as_read(self.request.user, self.kwargs['pk'])
        return Response(self.serializer_class(notification).data)