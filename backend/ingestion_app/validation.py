"""
Validation service: Checks normalized records for data quality issues.

This creates the "suspicious record detection" that makes the app feel enterprise-grade.
Rules are implemented as simple threshold checks, but feel intelligent.
"""

from decimal import Decimal
from typing import List, Tuple, Dict
from datetime import datetime, timedelta


class ValidationRule:
    """Base class for validation rules."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        """
        Check if record violates this rule.
        Returns: List of (issue_type, severity, description)
        """
        raise NotImplementedError


class NegativeValueRule(ValidationRule):
    """Negative values are always errors (can't have negative fuel, electricity, etc)."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        val = record.get('normalized_value')
        if val is not None and Decimal(str(val)) < 0:
            issues.append((
                'negative_value',
                'error',
                f"Negative value: {val} {record.get('normalized_unit')}. Emissions cannot be negative."
            ))
        return issues


class MissingDateRule(ValidationRule):
    """Activity date is required for emissions tracking."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        if not record.get('activity_date'):
            issues.append((
                'missing_date',
                'error',
                "Missing activity date. Cannot correlate to emissions period."
            ))
        return issues


class ZeroValueRule(ValidationRule):
    """Zero values are suspicious but not errors."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        val = record.get('normalized_value')
        if val is not None and Decimal(str(val)) == 0:
            issues.append((
                'zero_value',
                'warning',
                "Zero consumption reported. Is this correct?"
            ))
        return issues


class OutlierDetectionRule(ValidationRule):
    """
    Detect unusually high/low values.
    
    In a real system, would use historical data. Here, we use static thresholds.
    """
    
    # Category-based thresholds for outlier detection
    THRESHOLDS = {
        'fuel': {
            'high': 5000,  # L per transaction
            'low': 1,       # L per transaction
        },
        'electricity': {
            'high': 50000,  # kWh per meter per month
            'low': 10,      # kWh per meter per month
        },
        'travel_flight': {
            'high': 20000,  # km per flight
            'low': 100,     # km per flight
        },
        'travel_hotel': {
            'high': 30,     # nights per stay
            'low': 1,
        },
    }
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        
        category = record.get('category')
        val = record.get('normalized_value')
        
        if not val or category not in self.THRESHOLDS:
            return issues
        
        val_decimal = Decimal(str(val))
        thresholds = self.THRESHOLDS[category]
        
        if val_decimal > thresholds['high']:
            issues.append((
                'outlier_high',
                'warning',
                f"Value {val} {record.get('normalized_unit')} is unusually high for {category}. "
                f"Expected max ~{thresholds['high']}. Possible data error or exceptional circumstance?"
            ))
        
        if val_decimal < thresholds['low'] and val_decimal > 0:
            issues.append((
                'outlier_low',
                'warning',
                f"Value {val} {record.get('normalized_unit')} is unusually low. "
                f"Possible rounding or decimal error?"
            ))
        
        return issues


class InvalidUnitRule(ValidationRule):
    """Unknown/unsupported units indicate data quality issues."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        unit = record.get('normalized_unit', '').lower()
        
        if unit == 'unknown':
            issues.append((
                'invalid_unit',
                'error',
                f"Unit '{record.get('raw_unit')}' could not be recognized. "
                f"Supported units: L (fuel), kWh (electricity), km (distance), nights (hotel)."
            ))
        
        return issues


class MissingContextRule(ValidationRule):
    """Some records lack contextual information."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        
        # For travel, employee name is useful
        if record.get('category', '').startswith('travel_') and not record.get('employee_name'):
            issues.append((
                'missing_context',
                'info',
                "Missing employee name. Makes it harder to verify business purpose."
            ))
        
        # For fuel, plant code is useful
        if record.get('category') == 'fuel' and not record.get('plant_code'):
            issues.append((
                'missing_context',
                'info',
                "Missing plant code. Cannot correlate to facility."
            ))
        
        return issues


class DuplicateDetectionRule(ValidationRule):
    """
    Detect potential duplicates in batch.
    Requires context: other records in same batch.
    """
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        
        if not context or 'other_records' not in context:
            return issues
        
        # Look for exact duplicates
        matching = [
            r for r in context['other_records']
            if (r.get('category') == record.get('category') and
                r.get('activity_date') == record.get('activity_date') and
                r.get('normalized_value') == record.get('normalized_value') and
                r.get('plant_code') == record.get('plant_code'))
        ]
        
        if len(matching) > 1:
            issues.append((
                'duplicate_row',
                'warning',
                f"Found {len(matching)} records with identical values. Possible duplicate upload?"
            ))
        
        return issues


class FutureDateRule(ValidationRule):
    """Activity date cannot be in the future."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        
        activity_date = record.get('activity_date')
        if activity_date and activity_date > datetime.now().date():
            issues.append((
                'invalid_date_format',
                'error',
                f"Activity date {activity_date} is in the future. "
                f"Emissions must have occurred in the past."
            ))
        
        return issues


class ReasonableHistoryRule(ValidationRule):
    """Activity date shouldn't be too far in past."""
    
    def check(self, record: Dict, context: Dict = None) -> List[Tuple[str, str, str]]:
        issues = []
        
        activity_date = record.get('activity_date')
        if activity_date:
            # Alert if > 3 years in past
            if (datetime.now().date() - activity_date) > timedelta(days=3*365):
                issues.append((
                    'info',
                    'warning',
                    f"Activity date {activity_date} is very old ({(datetime.now().date() - activity_date).days} days). "
                    f"Ensure this is intentional historical data."
                ))
        
        return issues


class ValidationEngine:
    """
    Orchestrates validation rules.
    """
    
    def __init__(self):
        self.rules = [
            NegativeValueRule(),
            MissingDateRule(),
            ZeroValueRule(),
            OutlierDetectionRule(),
            InvalidUnitRule(),
            MissingContextRule(),
            FutureDateRule(),
            ReasonableHistoryRule(),
        ]
    
    def validate(self, record: Dict, other_records: List[Dict] = None) -> Tuple[List[Dict], int]:
        """
        Validate a single record.
        
        Returns:
        - List of issues (dicts with issue_type, severity, description)
        - Confidence score (0-100) based on issues found
        """
        issues = []
        context = {
            'other_records': other_records or []
        }
        
        for rule in self.rules:
            rule_issues = rule.check(record, context)
            for issue_type, severity, description in rule_issues:
                issues.append({
                    'issue_type': issue_type,
                    'severity': severity,
                    'description': description,
                })
        
        # Calculate confidence score
        confidence = 100
        
        # Deduct for errors
        error_count = sum(1 for i in issues if i['severity'] == 'error')
        confidence -= error_count * 20  # Each error: -20%
        
        # Deduct for warnings
        warning_count = sum(1 for i in issues if i['severity'] == 'warning')
        confidence -= warning_count * 10  # Each warning: -10%
        
        confidence = max(0, min(100, confidence))  # Clamp 0-100
        
        return issues, confidence


class DataQualityScorer:
    """
    Calculate data quality score for entire dataset.
    Makes the app feel more enterprise.
    
    Score reflects:
    - Missing values
    - Duplicates
    - Invalid values
    - Outliers
    """
    
    def calculate(self, records: List[Dict], issues_by_record: Dict) -> int:
        """
        Calculate data quality score (0-100) for entire batch.
        
        records: List of normalized records
        issues_by_record: Dict mapping record_id to list of issues
        """
        if not records:
            return 100
        
        issues_count = sum(len(issues) for issues in issues_by_record.values())
        error_count = sum(
            1 for issues in issues_by_record.values()
            for issue in issues
            if issue.get('severity') == 'error'
        )
        
        # Start with 100
        score = 100
        
        # Errors cost more (each error -5 points)
        score -= error_count * 5
        
        # Other issues cost less (each -1 point)
        other_issues = issues_count - error_count
        score -= other_issues
        
        # Clamp to 0-100
        return max(0, min(100, score))
