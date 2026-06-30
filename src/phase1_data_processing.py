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
        self.config_path = os.path.abspath(os.path.expanduser(config_path))
        self.input_file = os.path.abspath(os.path.expanduser(input_file))
        self.output_dir = os.path.abspath(os.path.expanduser(output_dir))
        
        # Initialize modules
        print("Initializing modules...")
        self.data_cleaner = DataCleaner(config_path)
        self.ubif_validator = UBIFValidator(config_path)
        self.compliance_engine = ComplianceEngine(config_path)
        self.interest_labeler = InterestLabeler(config_path)
        self.sessionizer = Sessionizer(window_minutes=30)
        self.feature_extractor = SessionFeatureExtractor()
        # Load processing preferences from config (optional)
        try:
            with open(config_path, 'r', encoding='utf-8') as cf:
                cfg = yaml.safe_load(cf) or {}
            self.stream_clean_first = bool(
                cfg.get('ubif_filters', {})
                   .get('processing', {})
                   .get('stream_clean_first', False)
            )
            self.shadow_legal_audit = bool(
                cfg.get('ubif_filters', {})
                   .get('processing', {})
                   .get('shadow_legal_audit', False)
            )
        except Exception:
            self.stream_clean_first = False
            self.shadow_legal_audit = False
        
        # Storage for intermediate results
        self.valid_records = []
        self.rejected_records = []
        self.step_durations = {}
        
        print("Pipeline initialized successfully!")
    
    def step_1_data_cleaning(self) -> List[Dict[str, Any]]:
        """
        Step 1.1: Data Cleaning
        
        Returns:
            Cleaned records (raw format)
        """
        print("\n=== STEP 1.1: DATA CLEANING ===")
        
        records = []
        total_read = 0
        
        # Read NDJSON file line by line (memory efficient for large files)
        if not os.path.exists(self.input_file):
            raise FileNotFoundError(f"Input file not found: {self.input_file}")

        print(f"Reading from {self.input_file}...")
        
        with open(self.input_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(tqdm(f, desc="Reading records")):
                if not line.strip():
                    continue
                
                try:
                    record = json.loads(line)
                    total_read += 1
                    
                    if self.stream_clean_first:
                        processed = self.data_cleaner.stream_process_record(record)
                        if processed is None:
                            # Dropped by cleaner; skip further processing
                            continue
                        records.append(processed)
                    else:
                        records.append(record)
                
                except json.JSONDecodeError as e:
                    print(f"JSON decode error at line {line_num + 1}: {str(e)}")
                    continue
                
                # Process in batches to avoid memory issues
                if len(records) % 10000 == 0 and len(records) > 0:
                    print(f"Loaded {len(records)} records...")

            print(f"✓ Input records: {total_read}")
        
        if self.stream_clean_first:
            self.data_cleaner.stats['total_input'] = total_read
            self.data_cleaner.stats['total_output'] = len(records)
            cleaner_stats = self.data_cleaner.get_stats()
            print(f"✓ Cleaned records: {len(records)}")
            print(f"  - Duplicates removed: {cleaner_stats['duplicates_removed']}")
            print(f"  - Test accounts removed: {cleaner_stats['test_accounts_removed']}")
            print(f"  - Bot traffic removed: {cleaner_stats['bot_traffic_removed']}")
            print(f"  - Missing serviceId removed: {cleaner_stats['missing_service_id_removed']}")
        else:
            print("Removing duplicates, test accounts, bot traffic...")
            records = self.data_cleaner.clean_all(records)
            cleaner_stats = self.data_cleaner.get_stats()
            print(f"✓ Cleaned records: {len(records)}")
            print(f"  - Duplicates removed: {cleaner_stats['duplicates_removed']}")
            print(f"  - Test accounts removed: {cleaner_stats['test_accounts_removed']}")
            print(f"  - Bot traffic removed: {cleaner_stats['bot_traffic_removed']}")
            print(f"  - Missing serviceId removed: {cleaner_stats['missing_service_id_removed']}")
        
        return records
    
    def step_2_ubif_validation(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.2: Data standards
        
        Args:
            records: Cleaned records from step 1
            
        Returns:
            List of valid records
        """
        print("\n=== STEP 1.2: Data standards ===")
        
        valid_records = []
        rejected_records = []
        
        for record_num, record in enumerate(tqdm(records, desc="Validating records"), start=1):
            # Validate record
            is_valid, violations = self.ubif_validator.validate_record(record)
            
            if is_valid:
                valid_records.append(record)
            else:
                rejected_records.append({
                    'line_number': record_num,
                    'record': record,
                    'violations': violations
                })
            
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
    
    def step_3_legal_compliance(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.3: Apply Legal Compliance (PDPA, Computer Crime Act)
        
        Args:
            records: Valid records from step 2
            
        Returns:
            Compliant records (anonymized)
        """
        print("\n=== STEP 1.3: LEGAL COMPLIANCE ===")
        
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

        
        # Save audit log
        audit_log = self.compliance_engine.generate_audit_log()
        audit_path = os.path.join(self.output_dir, 'compliance_audit_log.json')
        with open(audit_path, 'w', encoding='utf-8') as f:
            json.dump(audit_log, f, indent=2, ensure_ascii=False)

        if self.shadow_legal_audit and self.rejected_records:
            shadow_engine = ComplianceEngine(self.config_path)
            shadow_flagged = 0
            for entry in tqdm(self.rejected_records, desc="Shadow compliance (rejected)"):
                record = entry.get('record', entry)
                _processed, is_clean, _issues = shadow_engine.apply_all_rules(record)
                if not is_clean:
                    shadow_flagged += 1
            shadow_audit = shadow_engine.generate_audit_log()
            shadow_path = os.path.join(self.output_dir, 'compliance_audit_shadow.json')
            with open(shadow_path, 'w', encoding='utf-8') as f:
                json.dump(shadow_audit, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Compliant records: {len(compliant_records)}")
        print(f"⚠ Flagged records: {len(flagged_records)}")
        if self.shadow_legal_audit and self.rejected_records:
            print(
                "⚠ Shadow audit (rejected) records: "
                f"{len(self.rejected_records)} (flagged: {shadow_flagged})"
            )
        print(f"✓ Audit log saved to {audit_path}")
        
        return compliant_records
    
    def step_4_interest_labeling(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Step 1.4: Interest Labeling
        
        Args:
            records: Compliant records (raw format)
            
        Returns:
            Labeled records
        """
        print("\n=== STEP 1.4: INTEREST LABELING ===")
        
        parsed_records = []
        needs_parsing = True
        if records:
            sample = records[0]
            needs_parsing = not isinstance(sample, dict) or 'event_type' not in sample or 'timestamp' not in sample
        
        if needs_parsing:
            print("Parsing and extracting core fields...")
            for record in tqdm(records, desc="Parsing records"):
                extracted = DataParser.extract_core_fields(record)
                extracted = DataParser.handle_missing_values(extracted)
                extracted = DataParser.convert_types(extracted)
                
                # Only keep records with valid timestamp (product_id can be empty for non-product events)
                if extracted.get('timestamp') is not None:
                    parsed_records.append(extracted)
            print(f"✓ Parsed records: {len(parsed_records)}")
        else:
            parsed_records = records
        
        labeled = self.interest_labeler.apply_labels_to_records(parsed_records)
        
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
    
    def step_6_save_outputs(self, df) -> None:
        """
        Step 1.6: Save Output File (UBLDF)

        Args:
            df: Sessionized DataFrame with features
        """
        print("\n=== STEP 1.6: SAVING OUTPUTS ===")

        import pandas as pd

        if df is None or len(df) == 0:
            print("⚠ No records to save.")
            df = pd.DataFrame()

        # Sort by timestamp (if available) for stable ordering
        if 'timestamp' in df.columns:
            df = df.sort_values('timestamp').reset_index(drop=True)

        # Save UBLDF.json (full sessionized dataset)
        ubldf_path = os.path.join(self.output_dir, 'UBLDF.json')
        df.to_json(ubldf_path, orient='records', force_ascii=False, indent=2)
        print(f"✓ Saved {ubldf_path} ({len(df)} records)")

        interest_interested = int((df['interest'] == 1).sum()) if 'interest' in df.columns else 0
        interest_not = int((df['interest'] == 0).sum()) if 'interest' in df.columns else 0

        # Generate and save processing stats
        stats = {
            'total_input_records': self.ubif_validator.stats['total_processed'],
            'valid_records': self.ubif_validator.stats['valid'],
            'rejected_records': self.ubif_validator.stats['rejected'],
            'output_records': len(df),
            'interest_distribution': {
                'interest': interest_interested,
                'no_interest': interest_not
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
        
        # Step 1: Data Cleaning
        t1 = datetime.now()
        cleaned_records = self.step_1_data_cleaning()
        t2 = datetime.now()
        self.step_durations['step_1_data_cleaning'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 1 time: {self.step_durations['step_1_data_cleaning']:.2f} s")
        
        if not cleaned_records:
            print("ERROR: No records left after data cleaning. Exiting.")
            return
        
        # Step 2: UBIF Validation
        t1 = datetime.now()
        valid_records = self.step_2_ubif_validation(cleaned_records)
        t2 = datetime.now()
        self.step_durations['step_2_ubif_validation'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 2 time: {self.step_durations['step_2_ubif_validation']:.2f} s")
        
        if not valid_records:
            print("ERROR: No valid records found. Exiting.")
            return
        
        # Step 3: Legal Compliance
        t1 = datetime.now()
        compliant_records = self.step_3_legal_compliance(valid_records)
        t2 = datetime.now()
        self.step_durations['step_3_legal_compliance'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 3 time: {self.step_durations['step_3_legal_compliance']:.2f} s")
        
        # Step 4: Interest Labeling
        t1 = datetime.now()
        labeled_records = self.step_4_interest_labeling(compliant_records)
        t2 = datetime.now()
        self.step_durations['step_4_interest_labeling'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 4 time: {self.step_durations['step_4_interest_labeling']:.2f} s")
        
        # Step 5: Sessionization
        t1 = datetime.now()
        sessionized_df = self.step_5_sessionization(labeled_records)
        t2 = datetime.now()
        self.step_durations['step_5_sessionization'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 5 time: {self.step_durations['step_5_sessionization']:.2f} s")

        # Step 6: Save Outputs (UBLDF)
        t1 = datetime.now()
        self.step_6_save_outputs(sessionized_df)
        t2 = datetime.now()
        self.step_durations['step_6_save_outputs'] = (t2 - t1).total_seconds()
        print(f"⏱ Step 6 time: {self.step_durations['step_6_save_outputs']:.2f} s")
        
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
