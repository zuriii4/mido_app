from django.urls import path

from users.views import (
    BusinessUnitListView,
    MeView,
    ProfessionCategoryListView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('business-units/', BusinessUnitListView.as_view(), name='business-unit-list'),
    path('profession-categories/', ProfessionCategoryListView.as_view(), name='profession-category-list'),
    path('', UserListCreateView.as_view(), name='user-list'),
    path('<uuid:pk>/', UserDetailView.as_view(), name='user-detail'),
]
