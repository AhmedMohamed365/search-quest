from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# API V1
router_v1 = DefaultRouter()
router_v1.register(r'products', views.ProductViewSet, basename='product')

# API Version 1 URL patterns
urlpatterns = [
    path('v1/', include((router_v1.urls, 'api_v1'))),
] 