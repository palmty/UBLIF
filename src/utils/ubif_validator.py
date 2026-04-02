"""
UBIF Validator Module
Validates data according to UBIF standards including:
- ISO 8601 (datetime format)
- W3C584 (location coordinates)
- RFC 791/2460 (IP address)
- IEEE 802.1AR (device ID)
- ISO/IEC 20324:2012 (federated ID)
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import yaml


class UBIFValidator:
    """Main UBIF validation class"""
    
    def __init__(self, config_path: str):
        """
        Initialize validator with config
        
        Args:
            config_path: Path to config.yaml
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.ubif_config = self.config.get('ubif_filters', {})
        self.strict_mode = self.ubif_config.get('strict_mode', True)
        
        # Initialize sub-validators
        self.standards_checker = StandardsChecker(self.ubif_config)
        self.entity_validator = EntityValidator(self.ubif_config)
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'valid': 0,
            'rejected': 0,
            'violations': {}
        }
    
    def validate_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a single record
        
        Args:
            record: Record to validate
            
        Returns:
            (is_valid, list_of_violations)
        """
        violations = []
        
        self.stats['total_processed'] += 1
        
        # Check standards compliance
        standards_valid, standards_violations = self.standards_checker.check_all_standards(record)
        violations.extend(standards_violations)
        
        # Check entity validation
        entity_valid, entity_violations = self.entity_validator.validate_all_entities(record)
        violations.extend(entity_violations)
        
        # Update statistics
        for violation in violations:
            self.stats['violations'][violation] = self.stats['violations'].get(violation, 0) + 1
        
        # Determine if valid
        is_valid = len(violations) == 0
        
        if is_valid:
            self.stats['valid'] += 1
        else:
            self.stats['rejected'] += 1
        
        return is_valid, violations
    
    def get_validation_report(self) -> Dict[str, Any]:
        """
        Generate validation report
        
        Returns:
            Report dictionary
        """
        return {
            'total_records_processed': self.stats['total_processed'],
            'valid_records': self.stats['valid'],
            'rejected_records': self.stats['rejected'],
            'rejection_rate': self.stats['rejected'] / max(self.stats['total_processed'], 1),
            'violation_summary': self.stats['violations'],
            'timestamp': datetime.now().isoformat()
        }


class StandardsChecker:
    """Check standard compliance (ISO, W3C, RFC, IEEE)"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.standards = config.get('standards', [])
    
    def check_all_standards(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check all standards
        
        Args:
            record: Record to check
            
        Returns:
            (all_valid, list_of_violations)
        """
        violations = []
        
        for standard in self.standards:
            name = standard.get('name')
            required = standard.get('required', False)
            
            if name == 'ISO_8601':
                valid, msg = self.validate_iso8601(record, standard)
            elif name == 'W3C584':
                valid, msg = self.validate_w3c584(record, standard)
            elif name == 'RFC_791_2460':
                valid, msg = self.validate_rfc_ip(record, standard)
            elif name == 'IEEE_802_1AR':
                valid, msg = self.validate_ieee_device(record, standard)
            elif name == 'ISO_26324_2025':
                valid, msg = self.validate_iso_26324(record, standard)
            else:
                continue
            
            if not valid:
                if required:
                    violations.append(f"{name}: {msg}")
                # Non-required fields don't cause rejection but are flagged
        
        return len(violations) == 0, violations
    
    def validate_iso8601(self, record: Dict[str, Any], standard: Dict) -> Tuple[bool, str]:
        """Validate ISO 8601 datetime format"""
        field = standard.get('field', 'customValue.datetime')
        pattern = standard.get('pattern', r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:\d{2})?$')
        
        value = self._get_nested_field(record, field)
        
        if value is None:
            if not standard.get('required', False):
                return True, ""
            return False, "Field missing"
        
        if not re.match(pattern, str(value)):
            return False, f"Invalid datetime format: {value}"
        
        # Try to parse with various formats
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S'
        ]
        
        for fmt in formats:
            try:
                datetime.strptime(value.split('+')[0].split('-')[0:3] if '+' in value or value.count('-') > 2 else value, fmt)
                return True, ""
            except ValueError:
                continue
        
        # If we can parse it at all, accept it
        return True, ""
    
    def validate_w3c584(self, record: Dict[str, Any], standard: Dict) -> Tuple[bool, str]:
        """Validate W3C584 location coordinates"""
        fields = standard.get('fields', [])
        
        lat_value = self._get_nested_field(record, fields[0]) if len(fields) > 0 else None
        lon_value = self._get_nested_field(record, fields[1]) if len(fields) > 1 else None
        
        # If not required and missing, it's okay
        if lat_value is None or lon_value is None:
            if not standard.get('required', False):
                return True, ""
            return False, "Location coordinates missing"
        
        # Validate ranges
        try:
            lat = float(lat_value)
            lon = float(lon_value)
            
            if not (-90 <= lat <= 90):
                return False, f"Latitude out of range: {lat}"
            
            if not (-180 <= lon <= 180):
                return False, f"Longitude out of range: {lon}"
            
            return True, ""
        except (ValueError, TypeError):
            return False, "Invalid coordinate format"
    
    def validate_rfc_ip(self, record: Dict[str, Any], standard: Dict) -> Tuple[bool, str]:
        """Validate RFC 791/2460 IP address"""
        field = standard.get('field', 'customValue.serviceIP')
        pattern = standard.get('pattern', r'^(\d{1,3}\.){3}\d{1,3}$|^([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$')
        
        value = self._get_nested_field(record, field)
        
        if value is None:
            if not standard.get('required', False):
                return True, ""
            return False, "IP address missing"
        
        if not re.match(pattern, str(value)):
            return False, f"Invalid IP format: {value}"
        
        return True, ""
    
    def validate_ieee_device(self, record: Dict[str, Any], standard: Dict) -> Tuple[bool, str]:
        """Validate IEEE 802.1AR device identifier"""
        field = standard.get('field', 'customValue.device')
        
        value = self._get_nested_field(record, field)
        
        if value is None or str(value).strip() == "":
            if not standard.get('required', False):
                return True, ""
            return False, "Device identifier missing"
        
        return True, ""
    
    def validate_iso_26324(self, record: Dict[str, Any], standard: Dict) -> Tuple[bool, str]:
        """Validate ISO 26324:2025 federated identifier"""
        field = standard.get('field', 'customValue.serviceId')
        pattern = standard.get('pattern', r'^10\.\d{4,9}/\S+$')
        
        value = self._get_nested_field(record, field)
        
        if value is None or str(value).strip() == "":
            return False, "Federated identifier missing"

        if not re.match(pattern, str(value)):
            return False, f"Invalid DOI format: {value}"
        
        return True, ""
    
    def _get_nested_field(self, record: Dict, field_path: str) -> Optional[Any]:
        """Get nested field from record using dot notation"""
        parts = field_path.split('.')
        value = record
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
            
            if value is None:
                return None
        
        return value


class EntityValidator:
    """Validate base and supporting entities"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.base_entities = config.get('base_entities', {})
        self.supporting_entities = config.get('supporting_entities', {})
    
    def validate_all_entities(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate all entities
        
        Args:
            record: Record to validate
            
        Returns:
            (all_valid, list_of_violations)
        """
        violations = []
        
        # Validate base entities
        base_valid, base_violations = self.validate_base_entities(record)
        violations.extend(base_violations)
        
        # Validate supporting entities
        support_valid, support_violations = self.validate_supporting_entities(record)
        violations.extend(support_violations)
        
        return len(violations) == 0, violations
    
    def validate_base_entities(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate base entities (UsageLogs)"""
        violations = []
        
        usage_logs = self.base_entities.get('UsageLogs', {})
        required_fields = usage_logs.get('required_fields', [])
        validation_rules = usage_logs.get('validation', {})
        
        # Check required fields
        for field in required_fields:
            if field not in record or record[field] is None:
                violations.append(f"Required field missing: {field}")
        
        # Validate category
        if 'category' in validation_rules:
            category_rules = validation_rules['category']
            validation_type = category_rules.get('type', 'flexible')
            
            if validation_type == 'enum':
                # Strict enum validation
                allowed_values = category_rules.get('allowed_values', [])
                if record.get('category') not in allowed_values:
                    violations.append(f"Invalid category: {record.get('category')}")
            elif validation_type == 'flexible':
                # Flexible validation - just check if category exists and is not empty
                category = record.get('category')
                if not category or str(category).strip() == "":
                    violations.append("Category field is empty")
        
        # Validate name
        if 'name' in validation_rules:
            name_rules = validation_rules['name']
            # If max_length is not provided in config, do not enforce any length limit
            max_length = name_rules.get('max_length', None)
            
            name_value = record.get('name', '')
            
            # Skip strict pattern validation, just check if name exists; optionally enforce max_length if configured
            if not name_value or str(name_value).strip() == "":
                violations.append("Name field is empty")
            elif max_length is not None and len(str(name_value)) > max_length:
                violations.append(f"Name too long: {len(name_value)} > {max_length}")
        
        return len(violations) == 0, violations
    
    def validate_supporting_entities(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate supporting entities"""
        violations = []
        
        # Validate Service
        service_valid, service_violations = self._validate_service(record)
        violations.extend(service_violations)
        
        # Validate Device
        device_valid, device_violations = self._validate_device(record)
        violations.extend(device_violations)
        
        # Validate Location
        location_valid, location_violations = self._validate_location(record)
        violations.extend(location_violations)
        
        # Validate Keyword
        keyword_valid, keyword_violations = self._validate_keyword(record)
        violations.extend(keyword_violations)
        
        # Validate Datetime
        datetime_valid, datetime_violations = self._validate_datetime(record)
        violations.extend(datetime_violations)
        
        return len(violations) == 0, violations
    
    def _validate_service(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Service entity"""
        violations = []
        service_config = self.supporting_entities.get('Service', {})
        
        custom_value = record.get('customValue', {})
        
        # Service type validation
        service_type = custom_value.get('serviceType')
        if service_type:
            allowed_types = ['restaurant', 'hotel', 'homestay', 'tourist', 'activity', 'product', 'knowledge', 'business']
            if service_type not in allowed_types:
                violations.append(f"Invalid serviceType: {service_type}")
        
        return len(violations) == 0, violations
    
    def _validate_device(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Device entity"""
        violations = []
        device_config = self.supporting_entities.get('Device', {})
        
        custom_value = record.get('customValue', {})
        
        # Device validation
        device = custom_value.get('device')
        if device:
            device_pattern = r'^(IPhone|Android|Web|iPad|Desktop)$'
            if not re.match(device_pattern, str(device)):
                violations.append(f"Invalid device: {device}")
        
        # Operation validation
        operation = custom_value.get('operation')
        if operation:
            op_pattern = r'^(IOS|Android|Windows|MacOS|Linux)\s?\d*$'
            if not re.match(op_pattern, str(operation)):
                violations.append(f"Invalid operation: {operation}")
        
        return len(violations) == 0, violations
    
    def _validate_location(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Location entity"""
        violations = []
        custom_value = record.get('customValue', {})
        location = custom_value.get('location', {})
        
        if location and isinstance(location, dict):
            lat = location.get('lat')
            lon = location.get('lon')
            
            if lat is not None:
                try:
                    lat_float = float(lat)
                    if not (-90 <= lat_float <= 90):
                        violations.append(f"Latitude out of range: {lat}")
                except (ValueError, TypeError):
                    violations.append(f"Invalid latitude: {lat}")
            
            if lon is not None:
                try:
                    lon_float = float(lon)
                    if not (-180 <= lon_float <= 180):
                        violations.append(f"Longitude out of range: {lon}")
                except (ValueError, TypeError):
                    violations.append(f"Invalid longitude: {lon}")
        
        return len(violations) == 0, violations
    
    def _validate_keyword(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Keyword entity"""
        violations = []
        custom_value = record.get('customValue', {})
        keyword = custom_value.get('keyword', '')
        
        if keyword and len(str(keyword)) > 200:
            violations.append(f"Keyword too long: {len(keyword)} > 200")
        
        return len(violations) == 0, violations
    
    def _validate_datetime(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate Datetime entity"""
        violations = []
        datetime_config = self.supporting_entities.get('Datetime', {})
        
        custom_value = record.get('customValue', {})
        if not isinstance(custom_value, dict):
            # If customValue is not a dict or is missing, skip datetime validation
            return True, []
            
        datetime_str = custom_value.get('datetime')
        
        if datetime_str:
            # Try multiple datetime formats
            formats = [
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S'
            ]
            
            parsed = False
            dt = None
            for fmt in formats:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    parsed = True
                    break
                except ValueError:
                    continue
            
            if not parsed:
                # Try to accept it anyway if it looks like ISO format
                if re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', datetime_str):
                    parsed = True
            
            if not parsed:
                violations.append(f"Invalid datetime format: {datetime_str}")
            elif dt:
                # Check date range (only if we successfully parsed)
                min_date = datetime(2015, 1, 1)
                max_date = datetime(2030, 12, 31, 23, 59, 59)
                
                if not (min_date <= dt <= max_date):
                    violations.append(f"Datetime out of range: {datetime_str}")
        # If datetime is missing, that's okay - it's optional
        
        return len(violations) == 0, violations
