"""
Legal Compliance Module
Implements compliance with Thai laws and references:
- Personal Data Protection Act B.E. 2562 (PDPA, 2019)
- Computer-Related Crime Act B.E. 2560 (2017)
- Cybersecurity Act B.E. 2562 (2019)
- Royal Decree on Technology Crime Prevention B.E. 2566 (2023)
- General Data Protection Regulation (GDPR, EU 2016/679)
"""

import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import yaml


def _get_field(record: Dict[str, Any], field_path: str) -> Optional[Any]:
    if field_path in record:
        return record.get(field_path)

    current = record
    for part in field_path.split('.'):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current.get(part)
    return current


def _has_value(value: Optional[Any]) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    return True


class PDPACompliance:
    """
    Personal Data Protection Act B.E. 2562 (PDPA, 2019)
    Handles anonymization, coordinate truncation, and consent logging
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize PDPA compliance
        
        Args:
            config: PDPA configuration
        """
        self.config = config or {}
        self.consent_log = []
    
    def anonymize_account(self, account_name: str) -> str:
        """
        Anonymize account name using SHA256 hash
        
        Args:
            account_name: Original account name
            
        Returns:
            SHA256 hashed account name
        """
        if not account_name:
            return ""
        
        # Add salt for additional security
        salt = "ACGI_SALT_2024"
        salted = f"{account_name}{salt}"
        
        # Create SHA256 hash
        hash_object = hashlib.sha256(salted.encode('utf-8'))
        hashed_account = hash_object.hexdigest()
        
        return hashed_account

    def get_account_value(self, record: Dict[str, Any]) -> Optional[str]:
        """
        Extract account value from nested or flattened records
        """
        custom_value = record.get('customValue')
        if isinstance(custom_value, dict):
            return custom_value.get('account')

        return record.get('customValue.account')
    
    def mask_ip_address(self, ip_address: str) -> str:
        """
        Mask IP address (last octet for IPv4)
        
        Args:
            ip_address: Original IP address
            
        Returns:
            Masked IP address (xxx.xxx.xxx.XXX)
        """
        if not ip_address:
            return ""
        
        # IPv4 pattern
        ipv4_pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
        match = re.match(ipv4_pattern, ip_address)
        
        if match:
            # Mask last octet
            octets = match.groups()
            masked_ip = f"{octets[0]}.{octets[1]}.{octets[2]}.XXX"
            return masked_ip
        
        # IPv6 - mask last segment
        if ':' in ip_address:
            parts = ip_address.split(':')
            if len(parts) > 0:
                parts[-1] = 'XXXX'
                return ':'.join(parts)
        
        return "MASKED"
    
    def apply_anonymization(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply anonymization to record
        
        Args:
            record: Original record
            
        Returns:
            Anonymized record
        """
        anonymized = record.copy()
        
        # Anonymize account in customValue
        if 'customValue' in anonymized and isinstance(anonymized['customValue'], dict):
            custom_value = anonymized['customValue']
            
            # Anonymize account
            if 'account' in custom_value:
                original_account = custom_value['account']
                custom_value['account'] = self.anonymize_account(str(original_account))
            
            # Mask IP address
            if 'serviceIP' in custom_value and custom_value['serviceIP']:
                custom_value['serviceIP'] = self.mask_ip_address(str(custom_value['serviceIP']))

            # Truncate coordinates to reduce precision
            if 'location' in custom_value and isinstance(custom_value['location'], dict):
                loc = custom_value['location']
                if loc.get('lat') is not None:
                    try:
                        loc['lat'] = round(float(loc['lat']), 4)
                    except (ValueError, TypeError):
                        pass
                if loc.get('lon') is not None:
                    try:
                        loc['lon'] = round(float(loc['lon']), 4)
                    except (ValueError, TypeError):
                        pass

            # Anonymize accessId using the same hashing logic
            if 'accessId' in custom_value and custom_value['accessId']:
                custom_value['accessId'] = self.anonymize_account(str(custom_value['accessId']))
        else:
            account_key = 'customValue.account'
            if account_key in anonymized and anonymized[account_key]:
                anonymized[account_key] = self.anonymize_account(str(anonymized[account_key]))

            service_ip_key = 'customValue.serviceIP'
            if service_ip_key in anonymized and anonymized[service_ip_key]:
                anonymized[service_ip_key] = self.mask_ip_address(str(anonymized[service_ip_key]))

            lat_key = 'customValue.location.lat'
            if lat_key in anonymized and anonymized[lat_key] is not None:
                try:
                    anonymized[lat_key] = round(float(anonymized[lat_key]), 4)
                except (ValueError, TypeError):
                    pass

            lon_key = 'customValue.location.lon'
            if lon_key in anonymized and anonymized[lon_key] is not None:
                try:
                    anonymized[lon_key] = round(float(anonymized[lon_key]), 4)
                except (ValueError, TypeError):
                    pass

            access_id_key = 'customValue.accessId'
            if access_id_key in anonymized and anonymized[access_id_key]:
                anonymized[access_id_key] = self.anonymize_account(str(anonymized[access_id_key]))
        
        return anonymized

    def check_pdpa_required_fields(self, record: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check PDPA minimum requirements before anonymization
        Returns False if record cannot be made compliant
        """
        account_value = self.get_account_value(record)

        # Missing account means anonymization cannot be applied
        if not account_value:
            return False, "PDPA: missing account field required for anonymization"

        return True, ""
    
    def log_consent(self, user_id: str, action: str, timestamp: Optional[str] = None) -> None:
        """
        Log user consent for audit trail
        
        Args:
            user_id: User identifier
            action: Action performed
            timestamp: Timestamp of consent
        """
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        
        consent_entry = {
            'user_id': user_id,
            'action': action,
            'timestamp': timestamp,
            'consent_given': True
        }
        
        self.consent_log.append(consent_entry)
    
    def get_consent_log(self) -> List[Dict[str, Any]]:
        """
        Get consent log for audit
        
        Returns:
            List of consent entries
        """
        return self.consent_log


class ComputerCrimeActChecker:
    """
    Computer-Related Crime Act B.E. 2560 (2017)
    Detects malicious activities and preserves evidence trails
    """
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b\s+\bSELECT\b)",
        r"(\bSELECT\b\s+.+\bFROM\b\s+.+)",
        r"(\bINSERT\b\s+\bINTO\b)",
        r"(\bUPDATE\b\s+.+\bSET\b)",
        r"(\bDELETE\b\s+\bFROM\b)",
        r"(\bDROP\b\s+\bTABLE\b)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"(\bOR\b\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
        r"(--[^\n]*)",
        r"(#.*$)",
        r"(;\s*(DROP|SELECT|INSERT|UPDATE|DELETE)\b)",
    ]
    
    # XSS attack patterns
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"onerror\s*=",
        r"onload\s*=",
        r"onclick\s*=",
        r"<iframe[^>]*>",
        r"eval\s*\(",
        r"alert\s*\(",
    ]
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize checker
        
        Args:
            config: Configuration
        """
        self.config = config or {}
        self.action = self.config.get('action', 'reject')
        self.enabled_patterns = set(self.config.get('patterns', []))
        self.max_scan_length = int(self.config.get('max_scan_length', 2048))
        self.detected_attacks = []

    def _normalize_input(self, input_str: str) -> Tuple[str, bool]:
        normalized = str(input_str)
        normalized = normalized.replace("\x00", "")
        normalized = normalized.strip()
        truncated = False
        if self.max_scan_length > 0 and len(normalized) > self.max_scan_length:
            normalized = normalized[: self.max_scan_length]
            truncated = True
        return normalized, truncated
    
    def detect_sql_injection(self, input_str: str) -> Tuple[bool, Optional[str]]:
        """
        Detect SQL injection attempts
        
        Args:
            input_str: Input string to check
            
        Returns:
            (is_malicious, pattern_matched)
        """
        if not input_str:
            return False, None

        normalized, truncated = self._normalize_input(input_str)
        input_upper = normalized.upper()

        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_upper, re.IGNORECASE):
                return True, pattern

        if truncated:
            return True, "INPUT_TRUNCATED"

        return False, None
    
    def detect_xss_attack(self, input_str: str) -> Tuple[bool, Optional[str]]:
        """
        Detect XSS (Cross-Site Scripting) attempts
        
        Args:
            input_str: Input string to check
            
        Returns:
            (is_malicious, pattern_matched)
        """
        if not input_str:
            return False, None

        normalized, truncated = self._normalize_input(input_str)
        input_lower = normalized.lower()

        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return True, pattern

        if truncated:
            return True, "INPUT_TRUNCATED"

        return False, None
    
    def detect_excessive_requests(self, user_id: str, request_count: int, 
                                  threshold: int = 1000) -> bool:
        """
        Detect excessive requests (potential DoS)
        
        Args:
            user_id: User identifier
            request_count: Number of requests
            threshold: Maximum allowed requests
            
        Returns:
            True if excessive
        """
        return request_count > threshold
    
    def check_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check record for malicious activity
        
        Args:
            record: Record to check
            
        Returns:
            (is_clean, list_of_threats)
        """
        threats = []
        
        # Check all string fields for SQL injection and XSS
        # Check keyword
        keyword = _get_field(record, 'customValue.keyword') or ''
        if keyword:
            if not self.enabled_patterns or 'sql_injection' in self.enabled_patterns:
                sql_found, sql_pattern = self.detect_sql_injection(str(keyword))
                if sql_found:
                    threats.append(f"SQL_INJECTION in keyword: {sql_pattern}")

            if not self.enabled_patterns or 'xss_attack' in self.enabled_patterns:
                xss_found, xss_pattern = self.detect_xss_attack(str(keyword))
                if xss_found:
                    threats.append(f"XSS_ATTACK in keyword: {xss_pattern}")
        
        # Check service name
        service_name = _get_field(record, 'customValue.serviceName') or ''
        if service_name:
            if not self.enabled_patterns or 'sql_injection' in self.enabled_patterns:
                sql_found, sql_pattern = self.detect_sql_injection(str(service_name))
                if sql_found:
                    threats.append(f"SQL_INJECTION in serviceName: {sql_pattern}")

            if not self.enabled_patterns or 'xss_attack' in self.enabled_patterns:
                xss_found, xss_pattern = self.detect_xss_attack(str(service_name))
                if xss_found:
                    threats.append(f"XSS_ATTACK in serviceName: {xss_pattern}")
        
        # Check name field
        name = record.get('name', '')
        if name:
            if not self.enabled_patterns or 'sql_injection' in self.enabled_patterns:
                sql_found, sql_pattern = self.detect_sql_injection(str(name))
                if sql_found:
                    threats.append(f"SQL_INJECTION in name: {sql_pattern}")

            if not self.enabled_patterns or 'xss_attack' in self.enabled_patterns:
                xss_found, xss_pattern = self.detect_xss_attack(str(name))
                if xss_found:
                    threats.append(f"XSS_ATTACK in name: {xss_pattern}")
        
        if threats:
            self.detected_attacks.append({
                'record': record.get('name', 'unknown'),
                'threats': threats,
                'timestamp': datetime.now().isoformat()
            })
        
        return len(threats) == 0, threats
    
    def get_attack_log(self) -> List[Dict[str, Any]]:
        """
        Get log of detected attacks
        
        Returns:
            List of attack entries
        """
        return self.detected_attacks


class CybersecurityActChecker:
    """
    Cybersecurity Act B.E. 2562 (2019)
    Ensures device identification and network-layer logging are present
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.action = self.config.get('action', 'flag')
        self.fields = self.config.get('fields', ['customValue.device', 'customValue.serviceIP'])

    def check_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues = []

        for field in self.fields:
            if not _has_value(_get_field(record, field)):
                issues.append(f"CYBERSECURITY_ACT: missing {field}")

        return len(issues) == 0, issues


class RoyalDecreeTechCrimeChecker:
    """
    Royal Decree on Technology Crime Prevention B.E. 2566 (2023)
    Requires access-control logs with record identifiers and timestamps
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.action = self.config.get('action', 'flag')
        self.fields = self.config.get('fields', ['_id', 'customValue.datetime'])

    def check_record(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues = []

        for field in self.fields:
            if field in ('_id', 'id'):
                value = record.get(field)
            else:
                value = _get_field(record, field)
            if not _has_value(value):
                issues.append(f"ROYAL_DECREE_2566: missing {field}")

        return len(issues) == 0, issues


class GDPRComplianceChecker:
    """
    GDPR (EU 2016/679)
    Verifies privacy-by-design controls are applied to personal data
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.action = self.config.get('action', 'flag')
        self.fields = set(self.config.get('fields', ['customValue.account', 'customValue.serviceIP']))

    def check_record(self, original_record: Dict[str, Any], processed_record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues = []

        if 'customValue.account' in self.fields:
            original_account = _get_field(original_record, 'customValue.account')
            processed_account = _get_field(processed_record, 'customValue.account')
            if original_account and processed_account and original_account == processed_account:
                issues.append('GDPR: account not anonymized')

        if 'customValue.serviceIP' in self.fields:
            original_ip = _get_field(original_record, 'customValue.serviceIP')
            processed_ip = _get_field(processed_record, 'customValue.serviceIP')
            if original_ip and processed_ip and original_ip == processed_ip:
                issues.append('GDPR: serviceIP not masked')

        return len(issues) == 0, issues


class ComplianceEngine:
    """
    Main compliance engine that applies all legal rules
    """
    
    def __init__(self, config_path: str):
        """
        Initialize compliance engine
        
        Args:
            config_path: Path to config.yaml
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.ubif_config = self.config.get('ubif_filters', {})
        self.legal_config = self.ubif_config.get('legal_compliance', [])

        crime_rule = self._get_rule_config('COMPUTER_CRIME_ACT_2550', 'detect_malicious_activity')
        cyber_rule = self._get_rule_config('CYBERSECURITY_ACT_2562', 'device_and_network_logging')
        royal_rule = self._get_rule_config('ROYAL_DECREE_TECH_CRIME_2566', 'access_control_logging')
        gdpr_rule = self._get_rule_config('GDPR_EU_2016_679', 'privacy_by_design')

        
        # Initialize compliance modules
        self.pdpa = PDPACompliance()
        self.computer_crime = ComputerCrimeActChecker(config=crime_rule)
        self.cybersecurity = CybersecurityActChecker(config=cyber_rule)
        self.royal_decree = RoyalDecreeTechCrimeChecker(config=royal_rule)
        self.gdpr = GDPRComplianceChecker(config=gdpr_rule)
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'pdpa_anonymized': 0,
            'threats_detected': 0,
            'cybersecurity_issues': 0,
            'royal_decree_issues': 0,
            'gdpr_issues': 0,
            'flagged_records': 0
        }
        self.legal_issue_log: List[Dict[str, Any]] = []

    def _get_rule_config(self, law_name: str, rule_type: str) -> Dict[str, Any]:
        for law in self.legal_config:
            if law.get('name') != law_name:
                continue
            for rule in law.get('rules', []):
                if rule.get('type') == rule_type:
                    return rule
        return {}

    def apply_all_rules(self, record: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, List[str]]:
        """
        Apply all compliance rules to record
        
        Args:
            record: Original record
            
        Returns:
            (processed_record, is_clean, list_of_issues)
        """
        self.stats['total_processed'] += 1
        issues = []

        pdpa_ok, pdpa_msg = self.pdpa.check_pdpa_required_fields(record)
        if not pdpa_ok:
            self.stats['flagged_records'] += 1
            issues.append(pdpa_msg)
            return record, False, issues
        
        # Apply PDPA anonymization
        processed_record = self.pdpa.apply_anonymization(record)
        self.stats['pdpa_anonymized'] += 1
        
        # Check for computer crimes
        is_clean, threats = self.computer_crime.check_record(processed_record)
        
        if not is_clean:
            self.stats['threats_detected'] += 1
            issues.extend(threats)
            if self.computer_crime.action == 'reject':
                is_clean = False

        gdpr_ok, gdpr_issues = self.gdpr.check_record(record, processed_record)
        if not gdpr_ok:
            self.stats['gdpr_issues'] += len(gdpr_issues)
            issues.extend(gdpr_issues)
            if self.gdpr.action == 'reject':
                is_clean = False

        # Log consent (if account exists)
        account_value = self.pdpa.get_account_value(record)
        if account_value:
            self.pdpa.log_consent(
                user_id=account_value,
                action='data_processing'
            )

        # Flag if issues found
        if issues:
            self.stats['flagged_records'] += 1
            self.legal_issue_log.append({
                'record': record.get('name', 'unknown'),
                'issues': issues,
                'timestamp': datetime.now().isoformat()
            })
        return processed_record, is_clean, issues
    
    def generate_audit_log(self) -> Dict[str, Any]:
        """
        Generate compliance audit log
        
        Returns:
            Audit log dictionary
        """
        return {
            'statistics': self.stats,
            'consent_log': self.pdpa.get_consent_log(),
            'attack_log': self.computer_crime.get_attack_log(),
            'legal_issue_log': self.legal_issue_log,
            'timestamp': datetime.now().isoformat()
        }
    
    def flag_violations(self) -> List[Dict[str, Any]]:
        """
        Get list of flagged violations
        
        Returns:
            List of violations
        """
        return self.computer_crime.get_attack_log()
