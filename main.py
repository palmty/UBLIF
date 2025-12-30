#!/usr/bin/env python3
"""
Main Execution Script for Hybrid Recommendation System
Runs all three phases: Data Processing, Training, and Evaluation
"""

import sys
import os
import argparse
from datetime import datetime

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.phase1_data_processing import DataProcessingPipeline
from src.phase2_apriori_training import Phase2Pipeline
from src.phase3_evaluation import Phase3Pipeline


def print_banner():
    """Print project banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║       HYBRID RECOMMENDATION SYSTEM                           ║
    ║       (Apriori Graph + Custom XGBoost)                       ║
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


def run_phase2(config_path: str, train_path: str, output_dir: str):
    """Run Phase 2: Apriori Training"""
    print("\n" + "="*70)
    print("STARTING PHASE 2: APRIORI GRAPH + TRAINING")
    print("="*70)
    
    pipeline = Phase2Pipeline(config_path, train_path, output_dir)
    pipeline.run_full_pipeline()
    
    print("\n✓ Phase 2 completed successfully!")


def run_phase3(test_path: str, output_dir: str, viz_dir: str):
    """Run Phase 3: Evaluation"""
    print("\n" + "="*70)
    print("STARTING PHASE 3: EVALUATION + VISUALIZATION")
    print("="*70)
    
    pipeline = Phase3Pipeline(test_path, output_dir, viz_dir)
    pipeline.run_full_pipeline()
    
    print("\n✓ Phase 3 completed successfully!")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Hybrid Recommendation System - Complete Pipeline'
    )
    
    parser.add_argument(
        '--phase',
        type=str,
        choices=['all', '1', '2', '3'],
        default='all',
        help='Which phase to run (default: all)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='/Users/lab1/Documents/ACGI/config.yaml',
        help='Path to config.yaml'
    )
    
    parser.add_argument(
        '--input',
        type=str,
        default='/Users/lab1/Documents/ACGI/output_raw.ndjson',
        help='Path to input NDJSON file'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='/Users/lab1/Documents/ACGI/outputs',
        help='Path to output directory'
    )
    
    parser.add_argument(
        '--viz',
        type=str,
        default='/Users/lab1/Documents/ACGI/visualizations',
        help='Path to visualizations directory'
    )
    
    args = parser.parse_args()
    
    # Print banner
    print_banner()
    
    # Create output directories
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.viz, exist_ok=True)
    
    # Record start time
    start_time = datetime.now()
    print(f"\nStarting pipeline at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        if args.phase == 'all' or args.phase == '1':
            run_phase1(args.config, args.input, args.output)
        
        if args.phase == 'all' or args.phase == '2':
            train_path = os.path.join(args.output, 'train.json')
            
            if not os.path.exists(train_path):
                print(f"\nERROR: {train_path} not found. Run Phase 1 first.")
                sys.exit(1)
            
            run_phase2(args.config, train_path, args.output)
        
        if args.phase == 'all' or args.phase == '3':
            test_path = os.path.join(args.output, 'test.json')
            
            if not os.path.exists(test_path):
                print(f"\nERROR: {test_path} not found. Run Phase 1 first.")
                sys.exit(1)
            
            # Check if model artifacts exist
            rules_path = os.path.join(args.output, 'rules.json')
            if not os.path.exists(rules_path):
                print(f"\nERROR: {rules_path} not found. Run Phase 2 first.")
                sys.exit(1)
            
            run_phase3(test_path, args.output, args.viz)
        
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
        print(f"Visualizations:   {args.viz}")
        print("\n✓ All phases completed successfully!")
        print("\nNext steps:")
        print("  1. Review evaluation_report.html for results")
        print("  2. Check visualizations in the viz directory")
        print("  3. Analyze test_predictions.json for detailed predictions")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
