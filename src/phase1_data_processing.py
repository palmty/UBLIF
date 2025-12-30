"""
Phase 1: Data Processing Pipeline
Main script for UBIF validation, cleaning, sessionization, and train/test split
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
import yaml
from tqdm import tqdm

from utils.ubif_validator import UBIFValidator
from utils.legal_compliance import ComplianceEngine
from utils.data_cleaner import DataCleaner, DataParser, InterestLabeler
from utils.sessionizer import Sessionizer, SessionFeatureExtractor


class DataProcessingPipeline:
    """
    Complete data processing pipeline for Phase 1
    """
    
    def __init__(self, config_path: str, input_file: str, output_dir: str):
        """
        Initialize pipeline
        
        Args:
            config_path: Path to config.yaml
            input_file: Path to output_raw.ndjson
            output_dir: Path to outputs directory
        """
        self.config_path = config_path
        self.input_file = input_file
        self.output_dir = output_dir
        
        # Initialize modules
        print("Initializing modules...")
        self.ubif_validator = UBIFValidator(config_path)
        self.compliance_engine = ComplianceEngine(config_path)
        self.data_cleaner = DataCleaner(config_path)
        self.interest_labeler = InterestLabeler(config_path)
        self.sessionizer = Sessionizer(window_minutes=30)
        self.feature_extractor = SessionFeatureExtractor()
        # Load stream processing preference from config (optional)
        try:
            with open(config_path, 'r', encoding='utf-8') as cf:
                cfg = yaml.safe_load(cf) or {}
            self.stream_clean_first = bool(
                cfg.get('ubif_filters', {})
                   .get('processing', {})
                   .get('stream_clean_first', False)
            )
        except Exception:
            self.stream_clean_first = False
        
        # Storage for intermediate results
        self.valid_records = []
        self.rejected_records = []
        self.step_durations = {}
        
        print("Pipeline initialized successfully!")
    
    def step_1_ubif_validation(self) -> List[Dict[str, Any]]:
        """
        Step 1.1: UBIF Validation
        
        Returns:
            List of valid records
        """
        print("\n=== STEP 1.1: UBIF VALIDATION ===")
        
        valid_records = []
        rejected_records = []
        
        # Read NDJSON file line by line (memory efficient for large files)
        print(f"Reading from {self.input_file}...")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(tqdm(f, desc="Validating records")):
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    # Optional: apply streaming cleaning before validation to reduce memory
                    if self.stream_clean_first:
                        processed = self.data_cleaner.stream_process_record(record)
                        if processed is None:
                            # Dropped by cleaner; skip further processing
                            continue
                        record = processed
                    
                    # Validate record
                    is_valid, violations = self.ubif_validator.validate_record(record)
                    
                    if is_valid:
                        valid_records.append(record)
                    else:
                        rejected_records.append({
                            'line_number': line_num + 1,
                            'record': record,
                            'violations': violations
                        })
                
                except json.JSONDecodeError as e:
                    print(f"JSON decode error at line {line_num + 1}: {str(e)}")
                    continue
                
                # Process in batches to avoid memory issues
                if len(valid_records) % 10000 == 0 and len(valid_records) > 0:
                    print(f"Processed {len(valid_records)} valid records...")
        
        # Save validation report
        report = self.ubif_validator.get_validation_report()
        report_path = os.path.join(self.output_dir, 'ubif_validation_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Save rejected records (if any)
        if rejected_records:
            rejected_path = os.path.join(self.output_dir, 'rejected_records.json')
            with open(rejected_path, 'w', encoding='utf-8') as f:
                json.dump(rejected_records[:1000], f, indent=2, ensure_ascii=False)  # Save first 1000
        
        print(f"✓ Valid records: {len(valid_records)}")
        print(f"✗ Rejected records: {len(rejected_records)}")
        print(f"✓ Validation report saved to {report_path}")
        
        self.valid_records = valid_records
        self.rejected_records = rejected_records
        
        return valid_records
    
    def step_2_legal_compliance(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.2: Apply Legal Compliance (PDPA, Computer Crime Act)
        
        Args:
            records: Valid records from step 1
            
        Returns:
            Compliant records (anonymized)
        """
        print("\n=== STEP 1.2: LEGAL COMPLIANCE ===")
        
        compliant_records = []
        flagged_records = []
        
        for record in tqdm(records, desc="Applying compliance"):
            processed_record, is_clean, issues = self.compliance_engine.apply_all_rules(record)
            
            if is_clean:
                compliant_records.append(processed_record)
            else:
                flagged_records.append({
                    'record': processed_record,
                    'issues': issues
                })
                # Still include but flag
                compliant_records.append(processed_record)
        
        # Save audit log
        audit_log = self.compliance_engine.generate_audit_log()
        audit_path = os.path.join(self.output_dir, 'compliance_audit_log.json')
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump(audit_log, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Compliant records: {len(compliant_records)}")
        print(f"⚠ Flagged records: {len(flagged_records)}")
        print(f"✓ Audit log saved to {audit_path}")
        
        return compliant_records
    
    def step_3_data_cleaning(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.3: Data Cleaning & Parsing
        
        Args:
            records: Compliant records
            
        Returns:
            Cleaned and parsed records
        """
        print("\n=== STEP 1.3: DATA CLEANING / PARSING ===")
        
        # Apply cleaning (batch) only if streaming cleaning is disabled
        if self.stream_clean_first:
            print("Streaming cleaning enabled; skipping batch cleaning and proceeding to parsing.")
            cleaned = records
        else:
            print("Removing duplicates, test accounts, bot traffic...")
            cleaned = self.data_cleaner.clean_all(records)
        
        # Parse and extract core fields
        print("Parsing and extracting core fields...")
        parsed_records = []
        
        for record in tqdm(cleaned, desc="Parsing records"):
            extracted = DataParser.extract_core_fields(record)
            extracted = DataParser.handle_missing_values(extracted)
            extracted = DataParser.convert_types(extracted)
            
            # Only keep records with valid timestamp (product_id can be empty for non-product events)
            if extracted.get('timestamp') is not None:
                parsed_records.append(extracted)
        
        cleaner_stats = self.data_cleaner.get_stats()
        print(f"✓ Parsed records: {len(parsed_records)}")
        print(f"  - Duplicates removed: {cleaner_stats['duplicates_removed']}")
        print(f"  - Test accounts removed: {cleaner_stats['test_accounts_removed']}")
        print(f"  - Bot traffic removed: {cleaner_stats['bot_traffic_removed']}")
        
        return parsed_records
    
    def step_4_interest_labeling(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.4: Interest Labeling
        
        Args:
            records: Cleaned records
            
        Returns:
            Labeled records
        """
        print("\n=== STEP 1.4: INTEREST LABELING ===")
        
        labeled = self.interest_labeler.apply_labels_to_records(records)
        
        distribution = self.interest_labeler.get_interest_distribution(labeled)
        print(f"✓ Interest distribution:")
        print(f"  - Interest (1): {distribution['interest']}")
        print(f"  - No Interest (0): {distribution['no_interest']}")
        print(f"  - Interest rate: {distribution['interest_rate']:.2%}")
        
        return labeled
    
    def step_5_sessionization(self, records: List[Dict[str, Any]]) -> 'pd.DataFrame':
        """
        Step 1.5: Sessionization and Feature Extraction (vectorized DataFrame)
        Args:
            records: Labeled records (List[Dict])
        Returns:
            Sessionized records with features (pd.DataFrame)
        """
        import pandas as pd
        print("\n=== STEP 1.5: SESSIONIZATION ===")
        # Create sessions (returns list of dicts)
        print("Creating sessions (30-min window)...")
        sessionized = self.sessionizer.create_sessions(records)
        # Convert to DataFrame for vectorized feature extraction
        df = pd.DataFrame(sessionized)
        # Extract session features (returns DataFrame)
        print("Extracting session features...")
        featured_df = self.feature_extractor.extract_all_features(df)
        session_stats = self.sessionizer.get_stats()
        print(f"✓ Sessions created: {session_stats['total_sessions']}")
        print(f"  - Avg session length: {session_stats['avg_session_length']:.2f}")
        print(f"  - Min session length: {session_stats['min_session_length']}")
        print(f"  - Max session length: {session_stats['max_session_length']}")
        return featured_df
    
    def step_6_temporal_split(self, df, 
                             split_ratio: float = 0.8) -> tuple:
        """
        Step 1.6: Temporal Train/Test Split
        
        Args:
            df: Sessionized DataFrame with features
            split_ratio: Train/test split ratio (default: 0.8)
            
        Returns:
            (train_df, test_df)
        """
        print("\n=== STEP 1.6: TEMPORAL SPLIT ===")
        
        # Sort by timestamp
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        # Calculate split index
        split_idx = int(len(df) * split_ratio)
        
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        
        # Validate split
        if not train_df.empty and not test_df.empty:
            train_start = datetime.fromtimestamp(train_df.iloc[0]['timestamp'])
            train_end = datetime.fromtimestamp(train_df.iloc[-1]['timestamp'])
            test_start = datetime.fromtimestamp(test_df.iloc[0]['timestamp'])
            test_end = datetime.fromtimestamp(test_df.iloc[-1]['timestamp'])
            
            print(f"✓ Train set: {len(train_df)} records")
            print(f"  - Date range: {train_start} to {train_end}")
            
            print(f"✓ Test set: {len(test_df)} records")
            print(f"  - Date range: {test_start} to {test_end}")
            
            # Check class balance
            train_interest = (train_df['interest'] == 1).sum()
            test_interest = (test_df['interest'] == 1).sum()
            
            print(f"  - Train interest rate: {train_interest / len(train_df):.2%}")
            print(f"  - Test interest rate: {test_interest / len(test_df):.2%}")
        
        return train_df, test_df
    
    def step_7_save_outputs(self, train_df, test_df) -> None:
        """
        Step 1.7: Save Output Files
        
        Args:
            train_df: Training DataFrame
            test_df: Testing DataFrame
        """
        print("\n=== STEP 1.7: SAVING OUTPUTS ===")
        
        # Save train.json
        train_path = os.path.join(self.output_dir, 'train.json')
        train_df.to_json(train_path, orient='records', force_ascii=False, indent=2)
        print(f"✓ Saved {train_path}")
        
        # Save test.json
        test_path = os.path.join(self.output_dir, 'test.json')
        test_df.to_json(test_path, orient='records', force_ascii=False, indent=2)
        print(f"✓ Saved {test_path}")
        
        # Generate and save processing stats
        stats = {
            'total_input_records': self.ubif_validator.stats['total_processed'],
            'valid_records': self.ubif_validator.stats['valid'],
            'rejected_records': self.ubif_validator.stats['rejected'],
            'train_records': len(train_df),
            'test_records': len(test_df),
            'train_interest_distribution': {
                'interest': int((train_df['interest'] == 1).sum()),
                'no_interest': int((train_df['interest'] == 0).sum())
            },
            'test_interest_distribution': {
                'interest': int((test_df['interest'] == 1).sum()),
                'no_interest': int((test_df['interest'] == 0).sum())
            },
            'session_statistics': self.sessionizer.get_stats(),
            'cleaning_statistics': self.data_cleaner.get_stats(),
            'step_durations_seconds': self.step_durations,
            'generated_at': datetime.now().isoformat()
        }
        
        stats_path = os.path.join(self.output_dir, 'data_processing_stats.json')
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {stats_path}")
    
    def run_full_pipeline(self) -> None:
        """
        Run the complete Phase 1 pipeline
        """
        print("="*70)
        print("PHASE 1: DATA PROCESSING PIPELINE")
        print("="*70)
        
        start_time = datetime.now()
        
        # Step 1: UBIF Validation (with optional streaming cleaning during read)
        t1 = datetime.now()
        valid_records = self.step_1_ubif_validation()
        t2 = datetime.now()
        self.step_durations['step_1_ubif_validation'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 1 time: {self.step_durations['step_1_ubif_validation']:.2f} s")
        
        if not valid_records:
            print("ERROR: No valid records found. Exiting.")
            return
        
        # Step 2: Legal Compliance
        t1 = datetime.now()
        compliant_records = self.step_2_legal_compliance(valid_records)
        t2 = datetime.now()
        self.step_durations['step_2_legal_compliance'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 2 time: {self.step_durations['step_2_legal_compliance']:.2f} s")
        
        # Step 3: Data Cleaning / Parsing
        t1 = datetime.now()
        cleaned_records = self.step_3_data_cleaning(compliant_records)
        t2 = datetime.now()
        self.step_durations['step_3_cleaning_parsing'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 3 time: {self.step_durations['step_3_cleaning_parsing']:.2f} s")
        
        # Step 4: Interest Labeling
        t1 = datetime.now()
        labeled_records = self.step_4_interest_labeling(cleaned_records)
        t2 = datetime.now()
        self.step_durations['step_4_interest_labeling'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 4 time: {self.step_durations['step_4_interest_labeling']:.2f} s")
        
        # Step 5: Sessionization
        t1 = datetime.now()
        sessionized_df = self.step_5_sessionization(labeled_records)
        t2 = datetime.now()
        self.step_durations['step_5_sessionization'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 5 time: {self.step_durations['step_5_sessionization']:.2f} s")
        
        # Step 6: Temporal Split
        t1 = datetime.now()
        train_df, test_df = self.step_6_temporal_split(sessionized_df)
        t2 = datetime.now()
        self.step_durations['step_6_temporal_split'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 6 time: {self.step_durations['step_6_temporal_split']:.2f} s")
        
        # Step 7: Save Outputs
        t1 = datetime.now()
        self.step_7_save_outputs(train_df, test_df)
        t2 = datetime.now()
        self.step_durations['step_7_save_outputs'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 7 time: {self.step_durations['step_7_save_outputs']:.2f} s")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*70)
        print("PHASE 1 COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"Total processing time: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"\nOutput files saved to: {self.output_dir}")


def main():
    """Main entry point"""
    # Configuration
    config_path = '/Users/lab1/Documents/ACGI/config.yaml'
    input_file = '/Users/lab1/Documents/ACGI/output_raw.ndjson'
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    
    # Create output directory if not exists
    os.makedirs(output_dir, exist_ok=True)
    
    # Run pipeline
    pipeline = DataProcessingPipeline(config_path, input_file, output_dir)
    pipeline.run_full_pipeline()


if __name__ == '__main__':
    main()
