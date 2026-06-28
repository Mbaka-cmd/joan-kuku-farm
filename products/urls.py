from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'', views.ProductViewSet, basename='product')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'reviews', views.ProductReviewViewSet, basename='review')

urlpatterns = [
    path('', include(router.urls)),
]