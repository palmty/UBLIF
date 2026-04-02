"""
Phase 2: Apriori Training (no graph features)
This file forwards to the standard Phase 2 pipeline.
"""

import os

from phase2_apriori_training import Phase2Pipeline


def main():
    """Main entry point"""
    config_path = os.path.join(os.getcwd(), "config.yaml")
    train_path = os.path.join(os.getcwd(), "outputs", "train.json")
    output_dir = os.path.join(os.getcwd(), "outputs")

    pipeline = Phase2Pipeline(config_path, train_path, output_dir)
    pipeline.run_full_pipeline()


if __name__ == "__main__":
    main()
