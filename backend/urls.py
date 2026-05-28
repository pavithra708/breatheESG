"""
URL routing for API endpoints.
"""

from django.urls import path, include
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter
from .views import (
    UploadViewSet, RecordsViewSet, DashboardViewSet, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'upload', UploadViewSet, basename='upload')
router.register(r'records', RecordsViewSet, basename='records')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'audit-log', AuditLogViewSet, basename='audit-log')

def health_check(request):
    return JsonResponse({'status': 'ok'})

urlpatterns = [
    path('health/', health_check),
    path('api/', include(router.urls)),
]
