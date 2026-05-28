"""
Django REST Framework API endpoints.

Endpoints:
POST /upload/sap - Upload SAP fuel data
POST /upload/utility - Upload utility electricity data  
POST /upload/travel - Upload corporate travel data
GET /records - List all emission records
GET /records/{id} - Get single record
PATCH /records/{id}/approve - Analyst approves record
POST /records/{id}/lock - Lock record for audit
GET /dashboard - Dashboard metrics
GET /audit-log - Audit log entries
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from datetime import datetime
import json
from django.db import IntegrityError

from ingestion_app.models import (
    Tenant,
    DataSource,
    EmissionRecord,
    ValidationIssue,
    AuditLog,
    SourceType,
    RecordStatus,
    Scope,
    Category,
)
from .ingestion import IngestionPipeline, AuditLogger


class TenantSerializer:
    def __init__(self, tenant):
        self.data = {
            'id': tenant.id,
            'company_name': tenant.company_name,
        }


class DataSourceSerializer:
    def __init__(self, source):
        self.data = {
            'id': source.id,
            'source_type': source.source_type,
            'uploaded_by': source.uploaded_by,
            'uploaded_at': source.uploaded_at.isoformat(),
            'original_filename': source.original_filename,
            'row_count': source.row_count,
            'processing_status': source.processing_status,
            'error_message': source.error_message,
        }


class ValidationIssueSerializer:
    def __init__(self, issue):
        self.data = {
            'id': issue.id,
            'issue_type': issue.issue_type,
            'severity': issue.severity,
            'description': issue.description,
            'resolved': issue.resolved,
        }


class EmissionRecordSerializer:
    def __init__(self, record):
        self.data = {
            'id': record.id,
            'scope': record.scope,
            'category': record.category,
            'activity_type': record.activity_type,
            'normalized_value': None if record.normalized_value is None else str(record.normalized_value),
            'normalized_unit': record.normalized_unit,
            'activity_date': None if record.activity_date is None else record.activity_date.isoformat(),
            'status': record.status,
            'suspicious_flag': record.suspicious_flag,
            'confidence_score': record.confidence_score,
            'locked_for_audit': record.locked_for_audit,
            'issues': [ValidationIssueSerializer(i).data for i in record.issues.all()],
            'created_at': record.created_at.isoformat(),
        }


class UploadViewSet(viewsets.ViewSet):
    """
    Handles file uploads for three source types.
    """
    
    parser_classes = (MultiPartParser,)
    
    @action(detail=False, methods=['post'])
    def upload_sap(self, request):
        """Upload SAP fuel/procurement data."""
        return self._handle_upload('sap', request)
    
    @action(detail=False, methods=['post'])
    def upload_utility(self, request):
        """Upload utility electricity data."""
        return self._handle_upload('utility', request)
    
    @action(detail=False, methods=['post'])
    def upload_travel(self, request):
        """Upload corporate travel data."""
        return self._handle_upload('travel', request)
    
    def _handle_upload(self, source_type: str, request):
        """
        Common upload handler.
        
        Returns:
        - Ingestion results
        - Column mapping with confidence scores
        - Validation issues
        - Data quality score
        """
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        tenant_id = request.data.get('tenant_id', 1)  # Default for demo
        uploaded_by = request.data.get('uploaded_by', 'system')
        
        # Get or create tenant
        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            tenant = Tenant.objects.create(company_name=f'Company {tenant_id}')
        
        # Read file
        file_content = file.read()
        
        # Run ingestion pipeline
        try:
            pipeline = IngestionPipeline(source_type)
            ingestion_result = pipeline.ingest(
                file_content,
                uploaded_by=uploaded_by,
                filename=file.name,
            )
        except Exception as exc:
            return Response(
                {'success': False, 'error': 'Ingestion pipeline failed', 'details': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not ingestion_result['success']:
            return Response(
                {
                    'success': False,
                    'errors': ingestion_result['errors']
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create DataSource record (handle duplicate file uploads gracefully)
        try:
            data_source = DataSource.objects.create(
                tenant=tenant,
                source_type=source_type,
                uploaded_by=uploaded_by,
                original_filename=file.name,
                file_hash=ingestion_result['file_hash'],
                row_count=ingestion_result['row_count'],
                processing_status='processing',
            )
        except IntegrityError:
            existing = DataSource.objects.filter(file_hash=ingestion_result['file_hash']).order_by('-uploaded_at').first()
            return Response(
                {
                    'success': False,
                    'error': 'Duplicate upload detected (same file already uploaded)',
                    'file_hash': ingestion_result['file_hash'],
                    'existing_data_source_id': None if existing is None else existing.id,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except Exception as exc:
            return Response(
                {'success': False, 'error': 'Failed to create upload record', 'details': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Create EmissionRecords
        created_records = []

        try:
            for record_data in ingestion_result['normalized_records']:
                record = EmissionRecord.objects.create(
                    tenant=tenant,
                    data_source=data_source,
                    scope=record_data.get('scope', 'unknown'),
                    category=record_data.get('category') or 'other',
                    activity_type=record_data.get('activity_type') or 'Unknown Activity',
                    raw_value=record_data.get('raw_value') or '',
                    raw_unit=record_data.get('raw_unit') or '',
                    normalized_value=record_data.get('normalized_value'),
                    normalized_unit=record_data.get('normalized_unit'),
                    activity_date=record_data.get('activity_date'),
                    plant_code=record_data.get('plant_code') or '',
                    employee_name=record_data.get('employee_name') or '',
                    status=record_data.get('status', 'pending'),
                    suspicious_flag=record_data.get('suspicious_flag', False),
                    confidence_score=record_data.get('validation_confidence', 100),
                )

                # Create ValidationIssues
                for issue in ingestion_result['issues_by_record'].get(len(created_records), []):
                    ValidationIssue.objects.create(
                        record=record,
                        issue_type=issue['issue_type'],
                        severity=issue['severity'],
                        description=issue['description'],
                    )

                # Log creation
                AuditLog.objects.create(
                    record=record,
                    action='created',
                    changed_by=uploaded_by,
                    new_value=f'{record.category}: {record.normalized_value}',
                )

                created_records.append(EmissionRecordSerializer(record).data)
        except Exception as exc:
            data_source.processing_status = 'failed'
            data_source.error_message = str(exc)
            data_source.save()
            return Response(
                {
                    'success': False,
                    'error': 'Failed to persist normalized records',
                    'details': str(exc),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Mark data source as completed
        data_source.processing_status = 'completed'
        data_source.error_message = ''
        data_source.save()
        
        # Return results
        return Response({
            'success': True,
            'data_source_id': data_source.id,
            'rows_processed': ingestion_result['row_count'],
            'data_quality_score': ingestion_result['data_quality_score'],
            'column_mapping': ingestion_result['column_mapping'],
            'records': created_records,
        }, status=status.HTTP_201_CREATED)


class RecordsViewSet(viewsets.ViewSet):
    """
    Manage emission records.
    """
    
    def list(self, request):
        """List all records."""
        tenant_id = request.query_params.get('tenant_id', 1)
        status_filter = request.query_params.get('status')
        
        records = EmissionRecord.objects.filter(tenant_id=tenant_id)
        
        if status_filter:
            records = records.filter(status=status_filter)
        
        serialized = [EmissionRecordSerializer(r).data for r in records]
        
        return Response({
            'count': len(serialized),
            'results': serialized,
        })
    
    def retrieve(self, request, pk=None):
        """Get single record."""
        try:
            record = EmissionRecord.objects.get(id=pk)
            return Response(EmissionRecordSerializer(record).data)
        except EmissionRecord.DoesNotExist:
            return Response(
                {'error': 'Record not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        """Analyst approves record."""
        try:
            record = EmissionRecord.objects.get(id=pk)
            
            if record.locked_for_audit:
                return Response(
                    {'error': 'Record is locked for audit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if record has blocking issues
            blocking_issues = record.issues.filter(severity='error')
            if blocking_issues.exists():
                return Response(
                    {
                        'error': 'Cannot approve record with errors',
                        'issues': [ValidationIssueSerializer(i).data for i in blocking_issues]
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update status
            record.status = 'approved'
            record.save()
            
            # Log approval
            AuditLog.objects.create(
                record=record,
                action='approved',
                changed_by=request.data.get('changed_by', 'analyst'),
                field_name='status',
                old_value='pending',
                new_value='approved',
            )
            
            return Response(EmissionRecordSerializer(record).data)
        
        except EmissionRecord.DoesNotExist:
            return Response(
                {'error': 'Record not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        """Lock record for audit (immutable)."""
        try:
            record = EmissionRecord.objects.get(id=pk)
            
            if record.status != 'approved':
                return Response(
                    {'error': 'Only approved records can be locked'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Lock it
            record.locked_for_audit = True
            record.status = 'locked'
            record.save()
            
            # Log lock
            AuditLog.objects.create(
                record=record,
                action='locked',
                changed_by=request.data.get('changed_by', 'system'),
                field_name='locked_for_audit',
                old_value='False',
                new_value='True',
            )
            
            return Response(EmissionRecordSerializer(record).data)
        
        except EmissionRecord.DoesNotExist:
            return Response(
                {'error': 'Record not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class DashboardViewSet(viewsets.ViewSet):
    """
    Analytics dashboard.
    """
    
    @action(detail=False, methods=['get'])
    def metrics(self, request):
        """Get dashboard metrics."""
        try:
            tenant_id = int(request.query_params.get('tenant_id', 1))
            
            records = EmissionRecord.objects.filter(tenant_id=tenant_id)
            
            return Response({
                'total_records': records.count(),
                'pending_review': records.filter(status='pending').count(),
                'flagged': records.filter(status='flagged').count(),
                'approved': records.filter(status='approved').count(),
                'locked': records.filter(status='locked').count(),
                'suspicious': records.filter(suspicious_flag=True).count(),
                'by_source': {
                    'sap': records.filter(data_source__source_type='sap').count(),
                    'utility': records.filter(data_source__source_type='utility').count(),
                    'travel': records.filter(data_source__source_type='travel').count(),
                },
                'by_scope': {
                    '1': records.filter(scope='1').count(),
                    '2': records.filter(scope='2').count(),
                    '3': records.filter(scope='3').count(),
                },
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def data_sources(self, request):
        """Get list of all uploads."""
        tenant_id = request.query_params.get('tenant_id', 1)
        
        sources = DataSource.objects.filter(tenant_id=tenant_id)
        
        serialized = [DataSourceSerializer(s).data for s in sources]
        
        return Response({
            'count': len(serialized),
            'results': serialized,
        })


class AuditLogViewSet(viewsets.ViewSet):
    """
    Audit trail.
    """
    
    def list(self, request):
        """Get audit log."""
        tenant_id = request.query_params.get('tenant_id', 1)
        record_id = request.query_params.get('record_id')
        
        logs = AuditLog.objects.all()
        
        if record_id:
            logs = logs.filter(record_id=record_id)
        
        data = [
            {
                'id': log.id,
                'record_id': log.record_id,
                'action': log.action,
                'changed_by': log.changed_by,
                'field_name': log.field_name,
                'old_value': log.old_value,
                'new_value': log.new_value,
                'timestamp': log.timestamp.isoformat(),
            }
            for log in logs.order_by('-timestamp')[:100]
        ]
        
        return Response({
            'count': len(data),
            'results': data,
        })
