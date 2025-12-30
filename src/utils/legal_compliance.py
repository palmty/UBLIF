"""
Legal Compliance Module
Implements compliance with Thai laws:
- PDPA 2562 (Personal Data Protection Act)
- Computer Crime Act 2550
- Electronic Transaction Act
- Consumer Protection Act
"""

import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import yaml


class PDPACompliance:
    """
    PDPA 2562 (Personal Data Protection Act) Compliance
    Handles anonymization and consent management
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
        
        return anonymized
    
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
    Computer Crime Act 2550 Compliance
    Detects malicious activities
    """
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b.*\bWHERE\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(--\s*$)",
        r"(;\s*DROP)",
        r"(\bOR\b\s+\d+\s*=\s*\d+)",
        r"('\s*OR\s*'1'\s*=\s*'1)",
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
        self.detected_attacks = []
    
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
        
        input_upper = str(input_str).upper()
        
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, input_upper, re.IGNORECASE):
                return True, pattern
        
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
        
        input_lower = str(input_str).lower()
        
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, input_lower, re.IGNORECASE):
                return True, pattern
        
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
        custom_value = record.get('customValue', {})
        
        # Check keyword
        keyword = custom_value.get('keyword', '')
        if keyword:
            sql_found, sql_pattern = self.detect_sql_injection(str(keyword))
            if sql_found:
                threats.append(f"SQL_INJECTION in keyword: {sql_pattern}")
            
            xss_found, xss_pattern = self.detect_xss_attack(str(keyword))
            if xss_found:
                threats.append(f"XSS_ATTACK in keyword: {xss_pattern}")
        
        # Check service name
        service_name = custom_value.get('serviceName', '')
        if service_name:
            sql_found, sql_pattern = self.detect_sql_injection(str(service_name))
            if sql_found:
                threats.append(f"SQL_INJECTION in serviceName: {sql_pattern}")
            
            xss_found, xss_pattern = self.detect_xss_attack(str(service_name))
            if xss_found:
                threats.append(f"XSS_ATTACK in serviceName: {xss_pattern}")
        
        # Check name field
        name = record.get('name', '')
        if name:
            sql_found, sql_pattern = self.detect_sql_injection(str(name))
            if sql_found:
                threats.append(f"SQL_INJECTION in name: {sql_pattern}")
            
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
        
        # Initialize compliance modules
        self.pdpa = PDPACompliance()
        self.computer_crime = ComputerCrimeActChecker()
        
        # Statistics
        self.stats = {
            'total_processed': 0,
            'pdpa_anonymized': 0,
            'threats_detected': 0,
            'flagged_records': 0
        }
    
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
        
        # Apply PDPA anonymization
        processed_record = self.pdpa.apply_anonymization(record)
        self.stats['pdpa_anonymized'] += 1
        
        # Check for computer crimes
        is_clean, threats = self.computer_crime.check_record(record)
        
        if not is_clean:
            self.stats['threats_detected'] += 1
            issues.extend(threats)
        
        # Log consent (if account exists)
        custom_value = record.get('customValue', {})
        if 'account' in custom_value:
            self.pdpa.log_consent(
                user_id=custom_value['account'],
                action='data_processing'
            )
        
        # Flag if issues found
        if issues:
            self.stats['flagged_records'] += 1
        
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
            'timestamp': datetime.now().isoformat()
        }
    
    def flag_violations(self) -> List[Dict[str, Any]]:
        """
        Get list of flagged violations
        
        Returns:
            List of violations
        """
        return self.computer_crime.get_attack_log()
