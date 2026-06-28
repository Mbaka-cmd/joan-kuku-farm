from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.OrderViewSet, basename='order')

urlpatterns = [
    path('', include(router.urls)),
    path('track/<str:order_id>/', views.OrderTrackingView.as_view(), name='track_order'),
    path('cancel/<int:order_id>/', views.CancelOrderView.as_view(), name='cancel_order'),
]