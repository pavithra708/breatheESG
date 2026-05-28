"""
Ingestion service: Orchestrates the full pipeline.

Pipeline:
CSV Upload → Parse CSV → Normalize → Validate → Store → Flag Suspicious

This is where all the services work together.
"""

import csv
import hashlib
from io import StringIO, BytesIO
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from normalization import (
    SAPNormalizer, UtilityNormalizer, TravelNormalizer,
    ColumnMapper, DateParser
)
from validation import ValidationEngine, DataQualityScorer


class IngestionPipeline:
    """
    Main ingestion pipeline.
    
    Steps:
    1. Parse CSV file
    2. Analyze column headers (smart mapping)
    3. Normalize each row based on source type
    4. Validate normalized records
    5. Create EmissionRecord objects
    6. Create ValidationIssue objects
    7. Create AuditLog entries
    """
    
    def __init__(self, source_type: str):
        self.source_type = source_type
        self.validation_engine = ValidationEngine()
        self.quality_scorer = DataQualityScorer()
        
        # Select appropriate normalizer
        if source_type == 'sap':
            self.normalizer = SAPNormalizer()
        elif source_type == 'utility':
            self.normalizer = UtilityNormalizer()
        elif source_type == 'travel':
            self.normalizer = TravelNormalizer()
        else:
            raise ValueError(f"Unknown source type: {source_type}")
    
    def parse_csv(self, file_content: bytes) -> Tuple[List[str], List[Dict], Optional[str]]:
        """
        Parse CSV file.
        
        Returns:
        - headers (list of column names)
        - rows (list of dicts)
        - error (if parsing failed)
        """
        try:
            # Decode bytes to string
            content = file_content.decode('utf-8')
        except:
            try:
                # Try different encoding
                content = file_content.decode('latin1')
            except:
                return [], [], "Could not decode file. Please ensure it's a valid UTF-8 CSV."
        
        try:
            reader = csv.DictReader(StringIO(content))
            headers = reader.fieldnames
            rows = list(reader)
            
            if not headers:
                return [], [], "CSV file is empty or has no headers."
            
            return headers, rows, None
        
        except Exception as e:
            return [], [], f"CSV parsing error: {str(e)}"
    
    def calculate_file_hash(self, file_content: bytes) -> str:
        """Calculate SHA256 hash of file for deduplication."""
        return hashlib.sha256(file_content).hexdigest()
    
    def ingest(self, file_content: bytes, uploaded_by: str, filename: str) -> Dict:
        """
        Main ingestion method.
        
        Returns:
        {
            'success': bool,
            'file_hash': str,
            'row_count': int,
            'normalized_records': List[Dict],
            'issues_by_record': Dict[int, List[Dict]],  # record_idx -> issues
            'data_quality_score': int,
            'column_mapping': Dict[str, Tuple[str, int]],  # Shows mapping confidence
            'errors': List[str],
        }
        """
        result = {
            'success': False,
            'file_hash': self.calculate_file_hash(file_content),
            'row_count': 0,
            'normalized_records': [],
            'issues_by_record': {},
            'data_quality_score': 0,
            'column_mapping': {},
            'errors': [],
        }
        
        # Parse CSV
        headers, rows, parse_error = self.parse_csv(file_content)
        
        if parse_error:
            result['errors'].append(parse_error)
            return result
        
        if not rows:
            result['errors'].append("CSV file contains no data rows.")
            return result
        
        # Analyze columns (smart mapping)
        column_map = self.normalizer.analyze_columns(headers)
        result['column_mapping'] = {
            col: {'standard_field': std, 'confidence': conf}
            for col, (std, conf) in column_map.items()
        }
        
        # Normalize each row
        all_normalized = []
        
        for row_idx, row in enumerate(rows):
            # Call appropriate normalizer
            if self.source_type == 'travel':
                # Travel expands to multiple records
                normalized_list = self.normalizer.normalize_row(row, column_map, row_idx)
            else:
                normalized = self.normalizer.normalize_row(row, column_map)
                normalized_list = [normalized]
            
            all_normalized.extend(normalized_list)
        
        result['row_count'] = len(all_normalized)
        result['normalized_records'] = all_normalized
        
        # Validate each record
        issues_by_record = {}
        
        for record_idx, record in enumerate(all_normalized):
            issues, confidence = self.validation_engine.validate(
                record,
                other_records=all_normalized
            )
            
            issues_by_record[record_idx] = issues
            record['validation_confidence'] = confidence
            
            # Flag as suspicious if there are issues
            if issues:
                record['suspicious_flag'] = True
            
            # Check if record has errors
            has_errors = any(i['severity'] == 'error' for i in issues)
            if has_errors:
                record['status'] = 'flagged'
            else:
                record['status'] = 'pending'
        
        result['issues_by_record'] = issues_by_record
        
        # Calculate data quality score
        quality_score = self.quality_scorer.calculate(all_normalized, issues_by_record)
        result['data_quality_score'] = quality_score
        
        result['success'] = True
        return result


class AuditLogger:
    """
    Logs all changes to records for compliance.
    """
    
    @staticmethod
    def log_creation(record, changed_by: str) -> Dict:
        """Log record creation."""
        return {
            'action': 'created',
            'changed_by': changed_by,
            'field_name': None,
            'old_value': None,
            'new_value': str(record),
            'timestamp': datetime.now(),
        }
    
    @staticmethod
    def log_update(record, field: str, old_value, new_value, changed_by: str) -> Dict:
        """Log field update."""
        return {
            'action': 'updated',
            'changed_by': changed_by,
            'field_name': field,
            'old_value': str(old_value),
            'new_value': str(new_value),
            'timestamp': datetime.now(),
        }
    
    @staticmethod
    def log_approval(record, changed_by: str) -> Dict:
        """Log analyst approval."""
        return {
            'action': 'approved',
            'changed_by': changed_by,
            'field_name': 'status',
            'old_value': 'pending',
            'new_value': 'approved',
            'timestamp': datetime.now(),
        }
    
    @staticmethod
    def log_lock(record, changed_by: str) -> Dict:
        """Log audit lock."""
        return {
            'action': 'locked',
            'changed_by': changed_by,
            'field_name': 'locked_for_audit',
            'old_value': 'False',
            'new_value': 'True',
            'timestamp': datetime.now(),
        }
