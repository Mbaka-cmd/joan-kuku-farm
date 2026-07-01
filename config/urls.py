from django.contrib import admin
from django.views.generic import TemplateView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from products.views import ProductViewSet, CategoryViewSet
from orders.views import OrderViewSet
from config.views import home

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('', TemplateView.as_view(template_name='index.html'), name='home'),
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
]

# Serves images, CSS, and JS from the frontend folder when running manage.py runserver
# This is what makes images visible at http://127.0.0.1:8000/
from django.views.static import serve as _fe_serve
from django.urls import re_path as _re_path
from pathlib import Path as _Path
_FRONTEND_DIR = _Path(__file__).resolve().parent.parent / 'frontend'
urlpatterns += [
    _re_path(
        r'^(?P<path>.+\.(jpg|jpeg|png|gif|webp|svg|ico|css|js))$',
        _fe_serve,
        {'document_root': _FRONTEND_DIR}
    ),
]
