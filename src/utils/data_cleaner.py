"""
Data Cleaner Module
Handles data cleaning, parsing, and interest labeling
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
import yaml


class DataCleaner:
    """
    Main data cleaning class
    Removes duplicates, test accounts, bot traffic, etc.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize data cleaner
        
        Args:
            config_path: Path to config.yaml
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.ubif_config = self.config.get('ubif_filters', {})
        self.data_quality = self.ubif_config.get('data_quality', [])
        
        # Load cleaning rules
        self.load_cleaning_rules()
        
        # Statistics
        self.stats = {
            'total_input': 0,
            'duplicates_removed': 0,
            'test_accounts_removed': 0,
            'bot_traffic_removed': 0,
            'missing_service_id_removed': 0,
            'total_output': 0
        }
        # State for streaming duplicate detection
        self._stream_seen_recent = {}
    
    def load_cleaning_rules(self):
        """Load cleaning rules from config"""
        self.remove_duplicates_enabled = False
        self.duplicate_window_seconds = 1
        
        self.remove_test_enabled = False
        self.test_patterns = []
        
        self.remove_bot_enabled = False
        self.bot_patterns = []
        
        for rule in self.data_quality:
            if rule.get('name') == 'remove_duplicates' and rule.get('enabled', False):
                self.remove_duplicates_enabled = True
                self.duplicate_window_seconds = rule.get('window_seconds', 1)
            
            elif rule.get('name') == 'remove_test_accounts' and rule.get('enabled', False):
                self.remove_test_enabled = True
                self.test_patterns = rule.get('patterns', [])
            
            elif rule.get('name') == 'remove_bot_traffic' and rule.get('enabled', False):
                self.remove_bot_enabled = True
                self.bot_patterns = rule.get('bot_patterns', [])
    
    def remove_duplicates(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate records within time window
        
        Args:
            records: List of records
            
        Returns:
            Cleaned list without duplicates
        """
        if not self.remove_duplicates_enabled:
            return records
        
        # Sort by timestamp first if available
        def get_timestamp(record):
            # Handle both nested and flattened dot notation
            dt_str = record.get('customValue.datetime', '')
            if not dt_str:
                cv = record.get('customValue', {})
                if isinstance(cv, dict):
                    dt_str = cv.get('datetime', '')
            
            if dt_str:
                try:
                    # Handle various ISO formats
                    dt_str = dt_str.replace('Z', '+00:00')
                    return datetime.fromisoformat(dt_str)
                except:
                    pass
            return datetime.min
        
        try:
            sorted_records = sorted(records, key=get_timestamp)
        except:
            sorted_records = records
        
        seen_recent = {}
        cleaned = []
        
        for record in sorted_records:
            # Create unique key from important fields (handle both formats)
            timestamp = get_timestamp(record)
            
            account = record.get('customValue.account', '')
            if not account:
                cv = record.get('customValue', {})
                account = cv.get('account', '') if isinstance(cv, dict) else ''
            
            service_id = record.get('customValue.serviceId', '')
            if not service_id:
                cv = record.get('customValue', {})
                service_id = cv.get('serviceId', '') if isinstance(cv, dict) else ''
            
            key = (
                account,
                service_id,
                record.get('name', ''),
                record.get('category', '')
            )
            
            # Convert to string for hashing
            key_str = str(key)
            
            # Check if we've seen this key recently (within window)
            is_duplicate = False
            if key_str in seen_recent:
                last_time = seen_recent[key_str]
                time_diff = (timestamp - last_time).total_seconds()
                if time_diff <= self.duplicate_window_seconds:
                    is_duplicate = True
            
            if not is_duplicate:
                seen_recent[key_str] = timestamp
                cleaned.append(record)
            else:
                self.stats['duplicates_removed'] += 1
        
        return cleaned

    def _parse_record_timestamp(self, record: Dict[str, Any]) -> int:
        """Parse timestamp from record for streaming ops; returns epoch seconds or 0."""
        dt_str = record.get('customValue.datetime', '')
        if not dt_str:
            cv = record.get('customValue', {})
            if isinstance(cv, dict):
                dt_str = cv.get('datetime', '')
        if dt_str:
            try:
                dt_str_mod = str(dt_str).replace('Z', '+00:00')
                return int(datetime.fromisoformat(dt_str_mod).timestamp())
            except Exception:
                pass
        return 0

    def stream_process_record(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Apply cleaning filters incrementally to a single record during streaming.

        Returns None if the record should be dropped, otherwise returns the (possibly unchanged) record.
        """
        # Remove test/admin accounts
        if self.remove_test_enabled:
            custom_value = record.get('customValue', {})
            account = str(custom_value.get('account', '')).lower()
            for pattern in self.test_patterns:
                if pattern.lower() in account:
                    self.stats['test_accounts_removed'] += 1
                    return None

        # Remove bot/crawler traffic
        if self.remove_bot_enabled:
            custom_value = record.get('customValue', {})
            device = str(custom_value.get('device', '')).lower()
            operation = str(custom_value.get('operation', '')).lower()
            for pattern in self.bot_patterns:
                if pattern.lower() in device or pattern.lower() in operation:
                    self.stats['bot_traffic_removed'] += 1
                    return None

        # Filter missing serviceId
        service_id = record.get('customValue.serviceId', '')
        if not service_id:
            cv = record.get('customValue', {})
            if isinstance(cv, dict):
                service_id = cv.get('serviceId', '')
        if service_id is None or not str(service_id).strip() or str(service_id).lower() == 'null':
            self.stats['missing_service_id_removed'] += 1
            return None

        # Streaming duplicate check within time window
        if self.remove_duplicates_enabled:
            timestamp = self._parse_record_timestamp(record)
            cv = record.get('customValue', {})
            account = record.get('customValue.account', '') or (cv.get('account', '') if isinstance(cv, dict) else '')
            service_id = record.get('customValue.serviceId', '') or (cv.get('serviceId', '') if isinstance(cv, dict) else '')
            key = (account, service_id, record.get('name', ''), record.get('category', ''))
            key_str = str(key)

            last_time = self._stream_seen_recent.get(key_str)
            if last_time is not None:
                time_diff = abs(timestamp - last_time)
                if time_diff <= self.duplicate_window_seconds:
                    self.stats['duplicates_removed'] += 1
                    # Update last seen to the max timestamp to keep window moving forward
                    self._stream_seen_recent[key_str] = max(timestamp, last_time)
                    return None
            # First time seen or outside window: keep and update state
            self._stream_seen_recent[key_str] = timestamp

        return record
    
    def remove_test_accounts(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove test/admin accounts
        
        Args:
            records: List of records
            
        Returns:
            Cleaned list without test accounts
        """
        if not self.remove_test_enabled:
            return records
        
        cleaned = []
        
        for record in records:
            custom_value = record.get('customValue', {})
            account = str(custom_value.get('account', '')).lower()
            
            is_test = False
            for pattern in self.test_patterns:
                if pattern.lower() in account:
                    is_test = True
                    break
            
            if not is_test:
                cleaned.append(record)
            else:
                self.stats['test_accounts_removed'] += 1
        
        return cleaned
    
    def remove_bot_traffic(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove bot/crawler traffic
        
        Args:
            records: List of records
            
        Returns:
            Cleaned list without bot traffic
        """
        if not self.remove_bot_enabled:
            return records
        
        cleaned = []
        
        for record in records:
            custom_value = record.get('customValue', {})
            device = str(custom_value.get('device', '')).lower()
            operation = str(custom_value.get('operation', '')).lower()
            
            is_bot = False
            for pattern in self.bot_patterns:
                if pattern.lower() in device or pattern.lower() in operation:
                    is_bot = True
                    break
            
            if not is_bot:
                cleaned.append(record)
            else:
                self.stats['bot_traffic_removed'] += 1
        
        return cleaned
    
    def filter_missing_service_id(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter out records without serviceId
        
        Args:
            records: List of records
            
        Returns:
            Filtered list with only records that have serviceId
        """
        filtered = []
        
        for record in records:
            # Handle both nested and flattened dot notation
            service_id = record.get('customValue.serviceId', '')
            if not service_id:
                cv = record.get('customValue', {})
                if isinstance(cv, dict):
                    service_id = cv.get('serviceId', '')
            
            # Keep only records with non-null and non-empty serviceId
            if service_id is not None and str(service_id).strip() and str(service_id).lower() != 'null':
                filtered.append(record)
            else:
                self.stats['missing_service_id_removed'] += 1
        
        return filtered
    
    def validate_service_consistency(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate service consistency (serviceId matches serviceName)
        
        Args:
            records: List of records
            
        Returns:
            Validated list
        """
        # For now, just pass through
        # Could add more sophisticated validation
        return records
    
    def print_data_summary(self, before_count: int, after_count: int, stage: str = "processing") -> None:
        """
        Print data summary before and after processing
        
        Args:
            before_count: Number of records before
            after_count: Number of records after
            stage: Processing stage name
        """
        removed = before_count - after_count
        retention_rate = (after_count / before_count * 100) if before_count > 0 else 0
        
        print(f"\n📊 Data Summary ({stage}):")
        print(f"  ├─ ก่อนประมวลผล (Before):  {before_count:,} records")
        print(f"  ├─ หลังประมวลผล (After):   {after_count:,} records")
        print(f"  ├─ ลบออก (Removed):        {removed:,} records")
        print(f"  └─ อัตราคงเหลือ (Retention): {retention_rate:.2f}%")
    
    def clean_all(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply all cleaning operations
        
        Args:
            records: List of records
            
        Returns:
            Cleaned list
        """
        self.stats['total_input'] = len(records)
        initial_count = len(records)
        
        print(f"\n🧹 Starting data cleaning with {initial_count:,} records...")
        
        # Apply cleaning operations in sequence
        cleaned = records
        
        # Step 1: Remove duplicates
        before = len(cleaned)
        cleaned = self.remove_duplicates(cleaned)
        after = len(cleaned)
        if before != after:
            self.print_data_summary(before, after, "Remove Duplicates")
        
        # Step 2: Remove test accounts
        before = len(cleaned)
        cleaned = self.remove_test_accounts(cleaned)
        after = len(cleaned)
        if before != after:
            self.print_data_summary(before, after, "Remove Test Accounts")
        
        # Step 3: Remove bot traffic
        before = len(cleaned)
        cleaned = self.remove_bot_traffic(cleaned)
        after = len(cleaned)
        if before != after:
            self.print_data_summary(before, after, "Remove Bot Traffic")
        
        # Step 4: Filter missing serviceId (RE-ENABLED)
        before = len(cleaned)
        cleaned = self.filter_missing_service_id(cleaned)
        after = len(cleaned)
        self.print_data_summary(before, after, "Filter Missing ServiceId")
        
        # Step 5: Validate service consistency
        cleaned = self.validate_service_consistency(cleaned)
        
        self.stats['total_output'] = len(cleaned)
        
        # Final summary
        print(f"\n✅ Cleaning completed!")
        self.print_data_summary(initial_count, len(cleaned), "Overall Cleaning")
        
        return cleaned
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cleaning statistics"""
        return self.stats


class DataParser:
    """
    Parse and transform data fields
    """
    
    @staticmethod
    def parse_datetime_to_timestamp(datetime_str: str) -> Optional[int]:
        """
        Parse ISO 8601 datetime to Unix timestamp
        
        Args:
            datetime_str: Datetime string (2015-01-01T12:10:30Z)
            
        Returns:
            Unix timestamp (seconds since epoch)
        """
        if not datetime_str:
            return None
            
        try:
            # Try multiple formats
            formats = [
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%dT%H:%M:%S'
            ]
            
            for fmt in formats:
                try:
                    dt = datetime.strptime(datetime_str, fmt)
                    timestamp = int(dt.timestamp())
                    return timestamp
                except ValueError:
                    continue
            
            # Try fromisoformat as fallback
            try:
                dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
                return int(dt.timestamp())
            except:
                pass
                
            return None
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def extract_core_fields(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract core fields from record
        
        Args:
            record: Original record
            
        Returns:
            Extracted fields dictionary
        """
        # Handle both nested customValue and flattened dot notation
        custom_value = record.get('customValue', {})
        
        # Get datetime (try both formats)
        datetime_str = record.get('customValue.datetime', '')
        if not datetime_str and isinstance(custom_value, dict):
            datetime_str = custom_value.get('datetime', '')
        
        # Get account (device_id)
        device_id = record.get('customValue.account', '')
        if not device_id and isinstance(custom_value, dict):
            device_id = custom_value.get('account', '')
        
        # Get serviceId (product_id)
        product_id = record.get('customValue.serviceId', '')
        if not product_id and isinstance(custom_value, dict):
            product_id = custom_value.get('serviceId', '')
        
        # Get service name
        service_name = record.get('customValue.serviceName', '')
        if not service_name and isinstance(custom_value, dict):
            service_name = custom_value.get('serviceName', '')
        
        # Get service type
        service_type = record.get('customValue.serviceType', '')
        if not service_type and isinstance(custom_value, dict):
            service_type = custom_value.get('serviceType', '')
        
        # Get location (try both formats)
        location = record.get('customValue.location', None)
        if location is None and isinstance(custom_value, dict):
            location = custom_value.get('location', None)
        
        # Handle flattened location
        if location is None:
            lat = record.get('customValue.location.lat')
            lon = record.get('customValue.location.lon')
            if lat is not None and lon is not None:
                location = {'lat': lat, 'lon': lon}
        
        # Get keyword
        keyword = record.get('customValue.keyword', '')
        if not keyword and isinstance(custom_value, dict):
            keyword = custom_value.get('keyword', '')
        
        # Get device
        device = record.get('customValue.device', '')
        if not device and isinstance(custom_value, dict):
            device = custom_value.get('device', '')
        
        # Get operation
        operation = record.get('customValue.operation', '')
        if not operation and isinstance(custom_value, dict):
            operation = custom_value.get('operation', '')
        
        extracted = {
            'timestamp': DataParser.parse_datetime_to_timestamp(datetime_str),
            'device_id': str(device_id) if device_id else '',
            'product_id': str(product_id) if product_id else '',
            'event_type': record.get('name', ''),
            'category': record.get('category', ''),
            'service_name': str(service_name) if service_name else '',
            'service_type': str(service_type) if service_type else '',
            'location': location,
            'keyword': str(keyword) if keyword else '',
            'device': str(device) if device else '',
            'operation': str(operation) if operation else ''
        }
        
        return extracted
    
    @staticmethod
    def handle_missing_values(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle missing values
        
        Args:
            record: Record with potential missing values
            
        Returns:
            Record with handled missing values
        """
        handled = record.copy()
        
        # Set defaults for missing values
        if handled.get('location') is None:
            handled['location'] = None
        
        if handled.get('keyword') is None:
            handled['keyword'] = ""
        
        if handled.get('service_name') is None:
            handled['service_name'] = ""
        
        return handled
    
    @staticmethod
    def convert_types(record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert field types
        
        Args:
            record: Record to convert
            
        Returns:
            Record with converted types
        """
        converted = record.copy()
        
        # Ensure product_id is string
        if 'product_id' in converted and converted['product_id'] is not None:
            converted['product_id'] = str(converted['product_id'])
        
        # Ensure timestamp is int
        if 'timestamp' in converted and converted['timestamp'] is not None:
            try:
                converted['timestamp'] = int(converted['timestamp'])
            except (ValueError, TypeError):
                converted['timestamp'] = None
        
        # Ensure location coordinates are float
        if 'location' in converted and isinstance(converted['location'], dict):
            location = converted['location']
            if 'lat' in location:
                try:
                    location['lat'] = float(location['lat'])
                except (ValueError, TypeError):
                    location['lat'] = None
            
            if 'lon' in location:
                try:
                    location['lon'] = float(location['lon'])
                except (ValueError, TypeError):
                    location['lon'] = None
        
        return converted


class InterestLabeler:
    """
    Label records with interest flags based on event types
    """
    
    # Interest event types (31 types as specified)
    INTEREST_RULES = [
        'Activity/show',
        'product/ProductList/show',
        'communitydetail_Click',
        'travel/poi/show',
        'restaurant/show',
        'Home_Map_Click',
        'Home_search_Click',
        'restaurant/SearchList/show',
        'travel/SearchList/show',
        'product/SearchList/show',
        'Activity/SearchList/show',
        'travel/show',
        'product/show',
        'room/show',
        'knowledge/show',
        'business/show',
        'restaurant/detail/show',
        'travel/detail/show',
        'product/detail/show',
        'Activity/detail/show',
        'room/detail/show',
        'knowledge/detail/show',
        'business/detail/show',
        'Home_Category_Click',
        'Home_Recommend_Click',
        'Home_Popular_Click',
        'Home_Nearby_Click',
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize interest labeler
        
        Args:
            config_path: Optional path to config (can load custom rules)
        """
        self.interest_rules = set(self.INTEREST_RULES)
    
    def load_interest_rules(self, config: Dict[str, Any]) -> None:
        """
        Load interest rules from config
        
        Args:
            config: Configuration dictionary
        """
        # Could extend to load custom rules from config
        pass
    
    def label_interest(self, event_type: str) -> int:
        """
        Label whether event type indicates interest
        
        Args:
            event_type: Event type string
            
        Returns:
            1 if interest, 0 otherwise
        """
        if event_type in self.interest_rules:
            return 1
        return 0
    
    def apply_labels_to_records(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply interest labels to all records
        
        Args:
            records: List of records
            
        Returns:
            List of labeled records
        """
        labeled = []
        
        for record in records:
            labeled_record = record.copy()
            event_type = labeled_record.get('event_type', '')
            labeled_record['interest'] = self.label_interest(event_type)
            labeled.append(labeled_record)
        
        return labeled
    
    def get_interest_distribution(self, records: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Get distribution of interest labels
        
        Args:
            records: List of labeled records
            
        Returns:
            Distribution dictionary
        """
        interest_count = sum(1 for r in records if r.get('interest') == 1)
        no_interest_count = sum(1 for r in records if r.get('interest') == 0)
        
        return {
            'interest': interest_count,
            'no_interest': no_interest_count,
            'total': len(records),
            'interest_rate': interest_count / max(len(records), 1)
        }
