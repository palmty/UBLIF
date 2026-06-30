#!/usr/bin/env python3
"""
Main Execution Script for Data Processing Pipeline
Runs Phase 1: Data Processing (UBIF Validation, Compliance, Interest Labeling, Sessionization, UBLDF Output)
"""

import sys
import os
import argparse
import json
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.phase1_data_processing import DataProcessingPipeline


def print_banner():
    """Print project banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║       DATA PROCESSING PIPELINE                               ║
    ║       (Phase 1: UBIF Validation + Compliance)               ║
    ║                                                              ║
    ║       Version 1.0                                            ║
    ║       ACGI Project - 2025                                    ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)


def run_phase1(config_path: str, input_file: str, output_dir: str):
    """Run Phase 1: Data Processing"""
    print("\n" + "="*70)
    print("STARTING PHASE 1: DATA PROCESSING")
    print("="*70)

    pipeline = DataProcessingPipeline(config_path, input_file, output_dir)
    pipeline.run_full_pipeline()

    print("\n✓ Phase 1 completed successfully!")


def load_json_file(file_path: str):
    """Load JSON file and return parsed dict, or empty dict if unavailable."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def calculate_equation_results(output_dir: str):
    """Calculate metrics based on pipeline equation definitions."""
    stats_path = os.path.join(output_dir, 'data_processing_stats.json')
    compliance_path = os.path.join(output_dir, 'compliance_audit_log.json')
    validation_path = os.path.join(output_dir, 'ubif_validation_report.json')

    processing_stats = load_json_file(stats_path)
    compliance_audit = load_json_file(compliance_path)
    ubif_validation = load_json_file(validation_path)

    total_input_records = int(processing_stats.get('total_input_records', 0) or 0)
    valid_records = int(processing_stats.get('valid_records', 0) or 0)
    rejected_records = int(processing_stats.get('rejected_records', 0) or 0)

    cleaning_stats = processing_stats.get('cleaning_statistics', {}) or {}
    raw_input_records = int(
        processing_stats.get('raw_input_records', cleaning_stats.get('total_input', total_input_records)) or 0
    )

    compliance_stats = compliance_audit.get('statistics', {}) or {}
    flagged_records = int(compliance_stats.get('flagged_records', 0) or 0)
    pdpa_anonymized = int(compliance_stats.get('pdpa_anonymized', 0) or 0)
    threats_detected = int(compliance_stats.get('threats_detected', 0) or 0)

    # 1) Valid Records
    valid_processed_records = int(ubif_validation.get('valid_records', valid_records) or valid_records)

    # 2) Invalid Records
    records_failing_validation = rejected_records
    records_failing_compliance = flagged_records
    invalid_processed_records = records_failing_validation + records_failing_compliance

    # 3) Rejection Rate
    rejection_rate = (invalid_processed_records / raw_input_records * 100) if raw_input_records > 0 else 0.0

    # 4) Compliance Rate
    compliance_rate = (valid_processed_records / raw_input_records * 100) if raw_input_records > 0 else 0.0

    # 5) Validation Efficiency
    validation_efficiency = (valid_records / raw_input_records * 100) if raw_input_records > 0 else 0.0

    # 6) Overall Success Rate
    overall_success_rate = 100.0 - rejection_rate

    # 7) Legal Compliance Rate
    records_meeting_legal = max(pdpa_anonymized - threats_detected, 0)
    legal_compliance_rate = (
        (records_meeting_legal / valid_processed_records * 100)
        if valid_processed_records > 0 else 0.0
    )

    return {
        'raw_input_records': raw_input_records,
        'valid_records': valid_processed_records,
        'invalid_records': invalid_processed_records,
        'rejection_rate': rejection_rate,
        'compliance_rate': compliance_rate,
        'validation_efficiency': validation_efficiency,
        'overall_success_rate': overall_success_rate,
        'legal_compliance_rate': legal_compliance_rate,
    }


def print_equation_results(output_dir: str):
    """Print equation result block after successful pipeline run."""
    metrics = calculate_equation_results(output_dir)

    print("\n" + "="*70)
    print("EQUATION RESULTS")
    print("="*70)
    print(f"Total Input Records (raw):  {metrics['raw_input_records']:,}")
    print(f"Valid Records:               {metrics['valid_records']:,}")
    print(f"Invalid Records:             {metrics['invalid_records']:,}")
    print(f"Rejection Rate:              {metrics['rejection_rate']:.2f}%")
    print(f"Compliance Rate:             {metrics['compliance_rate']:.2f}%")
    print(f"Validation Efficiency:       {metrics['validation_efficiency']:.2f}%")
    print(f"Overall Success Rate:        {metrics['overall_success_rate']:.2f}%")
    print(f"Legal Compliance Rate:       {metrics['legal_compliance_rate']:.2f}%")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Data Processing Pipeline - Phase 1'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='config.yaml',
        help='Path to config.yaml'
    )

    parser.add_argument(
        '--input',
        type=str,
        default='output_raw.ndjson',
        help='Path to input NDJSON file'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='outputs',
        help='Path to output directory'
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Create output directory
    os.makedirs(args.output, exist_ok=True)

    # Record start time
    start_time = datetime.now()
    print(f"\nStarting pipeline at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    try:
        run_phase1(args.config, args.input, args.output)

        # Record end time
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Print summary
        print("\n" + "="*70)
        print("PIPELINE COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"\nStart time:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End time:    {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration:    {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"\nOutput directory: {args.output}")
        print_equation_results(args.output)
        print("\n✓ Phase 1 completed successfully!")
        print("\nNext steps:")
        print("  1. Review data_processing_stats.json for processing metrics")
        print("  2. Check ubif_validation_report.json and compliance_audit_log.json")
        print("  3. Launch the dashboard: streamlit run metrics_dashboard.py")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
