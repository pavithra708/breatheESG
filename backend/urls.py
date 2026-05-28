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
    return JsonResponse({'status': 'ok', 'message': 'API is running'})

def debug_info(request):
    """Debug endpoint to check if imports are working."""
    try:
        from ingestion_app.models import Tenant, EmissionRecord
        tenant_count = Tenant.objects.count()
        record_count = EmissionRecord.objects.count()
        return JsonResponse({
            'status': 'ok',
            'tenants': tenant_count,
            'records': record_count,
            'database': 'connected'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        }, status=500)

urlpatterns = [
    path('health/', health_check),
    path('debug/', debug_info),
    path('api/', include(router.urls)),
]
