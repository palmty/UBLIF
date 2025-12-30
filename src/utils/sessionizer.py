"""
Sessionizer Module
Creates sessions from user interactions and extracts session features
"""

import hashlib
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from collections import defaultdict


class Sessionizer:
    """
    Create sessions from user interactions based on time windows
    """
    
    def __init__(self, window_minutes: int = 30):
        """
        Initialize sessionizer
        
        Args:
            window_minutes: Session timeout window in minutes (default: 30)
        """
        self.window_minutes = window_minutes
        self.window_seconds = window_minutes * 60
        
        # Statistics
        self.stats = {
            'total_records': 0,
            'total_sessions': 0,
            'avg_session_length': 0,
            'min_session_length': 0,
            'max_session_length': 0
        }
    
    def sort_by_device_and_time(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort records by device_id and timestamp
        
        Args:
            records: List of records
            
        Returns:
            Sorted list
        """
        return sorted(
            records,
            key=lambda r: (r.get('device_id', ''), r.get('timestamp', 0))
        )
    
    def create_sessions(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create sessions from records using time window
        
        Args:
            records: List of sorted records
            
        Returns:
            List of records with session_id added
        """
        self.stats['total_records'] = len(records)
        
        if not records:
            return []
        
        # Sort first
        sorted_records = self.sort_by_device_and_time(records)
        
        # Group by device
        device_records = defaultdict(list)
        for record in sorted_records:
            device_id = record.get('device_id', 'unknown')
            device_records[device_id].append(record)
        
        # Create sessions for each device
        sessionized_records = []
        session_count = 0
        session_lengths = []
        
        for device_id, device_recs in device_records.items():
            if not device_recs:
                continue
            
            current_session_start = device_recs[0].get('timestamp', 0)
            current_session_records = []
            
            for record in device_recs:
                timestamp = record.get('timestamp', 0)
                
                # Check if we need to start a new session
                time_gap = timestamp - current_session_start
                
                if time_gap > self.window_seconds and current_session_records:
                    # Save current session
                    session_id = self.generate_session_id(device_id, current_session_start)
                    for sess_rec in current_session_records:
                        sess_rec['session_id'] = session_id
                    
                    sessionized_records.extend(current_session_records)
                    session_lengths.append(len(current_session_records))
                    session_count += 1
                    
                    # Start new session
                    current_session_start = timestamp
                    current_session_records = [record]
                else:
                    # Add to current session
                    current_session_records.append(record)
            
            # Don't forget the last session
            if current_session_records:
                session_id = self.generate_session_id(device_id, current_session_start)
                for sess_rec in current_session_records:
                    sess_rec['session_id'] = session_id
                
                sessionized_records.extend(current_session_records)
                session_lengths.append(len(current_session_records))
                session_count += 1
        
        # Update statistics
        self.stats['total_sessions'] = session_count
        if session_lengths:
            self.stats['avg_session_length'] = sum(session_lengths) / len(session_lengths)
            self.stats['min_session_length'] = min(session_lengths)
            self.stats['max_session_length'] = max(session_lengths)
        
        return sessionized_records
    
    def generate_session_id(self, device_id: str, start_time: int) -> str:
        """
        Generate unique session ID
        
        Args:
            device_id: Device identifier
            start_time: Session start timestamp
            
        Returns:
            Unique session ID
        """
        # Create hash from device_id + start_time
        key = f"{device_id}_{start_time}"
        hash_object = hashlib.md5(key.encode('utf-8'))
        session_id = hash_object.hexdigest()[:12]  # Use first 12 characters
        
        return session_id
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sessionization statistics"""
        return self.stats


class SessionFeatureExtractor:
    """
    Extract features from sessions
    """
    
    def __init__(self):
        """Initialize feature extractor"""
        pass
    
    def extract_all_features(self, df):
        """
        Extract all session features using Pandas DataFrame (vectorized).
        Args:
            df: DataFrame with sessionized records
        Returns:
            DataFrame with new features
        """
        import pandas as pd
        if df is None or len(df) == 0:
            return df
        # Ensure required columns exist
        for col in ['session_id', 'timestamp', 'product_id']:
            if col not in df.columns:
                df[col] = None
        # Sort by session and timestamp
        df = df.sort_values(['session_id', 'timestamp'], kind='mergesort').reset_index(drop=True)
        # Click position (1-indexed)
        df['click_position'] = df.groupby('session_id').cumcount() + 1
        # Session depth (group size)
        df['session_depth'] = df.groupby('session_id')['timestamp'].transform('size')
        # Session duration in minutes (max - min per session)
        session_max = df.groupby('session_id')['timestamp'].transform('max')
        session_min = df.groupby('session_id')['timestamp'].transform('min')
        df['session_duration_minutes'] = (session_max - session_min) / 60.0
        # Time since last click (in seconds)
        prev_ts = df.groupby('session_id')['timestamp'].shift(1)
        df['time_since_last_click'] = (df['timestamp'] - prev_ts).fillna(0).astype(int)
        # Previous products as list (per session, cumulative up to previous index)
        def _prev_products_per_session(g: pd.DataFrame) -> pd.Series:
            products = g['product_id'].tolist()
            prev_lists = [[p for p in products[:i] if p is not None] for i in range(len(products))]
            return pd.Series(prev_lists, index=g.index)
        df['previous_products'] = df.groupby('session_id', group_keys=False).apply(_prev_products_per_session)
        return df
    
    def calculate_click_position(self, record: Dict[str, Any], session: List[Dict[str, Any]]) -> int:
        """
        Calculate click position in session
        
        Args:
            record: Current record
            session: List of records in session
            
        Returns:
            Click position (1-indexed)
        """
        for idx, sess_record in enumerate(session):
            if sess_record is record:
                return idx + 1
        
        return 1
    
    def calculate_session_depth(self, session: List[Dict[str, Any]]) -> int:
        """
        Calculate total items in session
        
        Args:
            session: List of records in session
            
        Returns:
            Session depth
        """
        return len(session)
    
    def extract_previous_products(self, record: Dict[str, Any], 
                                  session: List[Dict[str, Any]]) -> List[str]:
        """
        Extract list of previous products in session
        
        Args:
            record: Current record
            session: List of records in session
            
        Returns:
            List of previous product IDs
        """
        previous = []
        
        for sess_record in session:
            if sess_record is record:
                break
            
            product_id = sess_record.get('product_id')
            if product_id:
                previous.append(product_id)
        
        return previous
    
    def calculate_session_duration(self, session: List[Dict[str, Any]]) -> float:
        """
        Calculate session duration in minutes
        
        Args:
            session: List of records in session
            
        Returns:
            Duration in minutes
        """
        if len(session) < 2:
            return 0.0
        
        # Sort by timestamp
        sorted_session = sorted(session, key=lambda r: r.get('timestamp', 0))
        
        start_time = sorted_session[0].get('timestamp', 0)
        end_time = sorted_session[-1].get('timestamp', 0)
        
        duration_seconds = end_time - start_time
        duration_minutes = duration_seconds / 60.0
        
        return duration_minutes
    
    def calculate_time_since_last_click(self, record: Dict[str, Any], 
                                       session: List[Dict[str, Any]]) -> int:
        """
        Calculate time since last click in seconds
        
        Args:
            record: Current record
            session: List of records in session
            
        Returns:
            Time gap in seconds
        """
        # Find current record index
        current_idx = -1
        for idx, sess_record in enumerate(session):
            if sess_record is record:
                current_idx = idx
                break
        
        if current_idx <= 0:
            return 0
        
        # Get previous record
        prev_record = session[current_idx - 1]
        
        time_gap = (
            record.get('timestamp', 0) - 
            prev_record.get('timestamp', 0)
        )
        
        return time_gap
