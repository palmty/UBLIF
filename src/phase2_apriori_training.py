"""
Phase 2: Apriori + Training
Transaction preparation, Apriori algorithm, and custom prediction
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set
from collections import defaultdict
from tqdm import tqdm
import numpy as np

# Import mlxtend for Apriori
try:
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder
except ImportError:
    print("WARNING: mlxtend not installed. Install with: pip install mlxtend")

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import pandas as pd


class TransactionBuilder:
    """
    Build transaction matrix from session data
    """
    
    def __init__(self, min_products: int = 2, max_products: int = 20):
        """
        Initialize transaction builder
        
        Args:
            min_products: Minimum products per session
            max_products: Maximum products per session
        """
        self.min_products = min_products
        self.max_products = max_products
        
        self.stats = {
            'total_records': 0,
            'total_sessions': 0,
            'filtered_sessions': 0,
            'avg_products_per_session': 0
        }
    
    def load_train_data(self, train_path: str) -> List[Dict[str, Any]]:
        """
        Load training data from JSON
        
        Args:
            train_path: Path to train.json
            
        Returns:
            List of training records
        """
        with open(train_path, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        self.stats['total_records'] = len(records)
        return records
    
    def group_by_session(self, records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """
        Group records by session and extract product IDs (serviceId)
        GOAL: Predict which specific serviceId users are interested in
        
        Args:
            records: List of records
            
        Returns:
            Dictionary mapping session_id to list of product_ids
        """
        sessions = defaultdict(list)
        
        for record in records:
            session_id = record.get('session_id')
            product_id = record.get('product_id')  # Use serviceId for product-level prediction
            
            if session_id and product_id:
                sessions[session_id].append(str(product_id))
        
        self.stats['total_sessions'] = len(sessions)
        return sessions
    
    def filter_sessions(self, sessions: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Filter sessions by length and remove duplicates
        
        Args:
            sessions: Dictionary of sessions
            
        Returns:
            Filtered sessions
        """
        filtered = {}
        
        for session_id, products in sessions.items():
            # Remove duplicates (keep unique products per session)
            unique_products = list(dict.fromkeys(products))  # Preserves order
            
            # Check length constraints
            if self.min_products <= len(unique_products) <= self.max_products:
                filtered[session_id] = unique_products
        
        self.stats['filtered_sessions'] = len(filtered)
        
        return filtered
    
    def create_transaction_matrix(self, sessions: Dict[str, List[str]]) -> List[List[str]]:
        """
        Create transaction matrix from sessions
        
        Args:
            sessions: Dictionary of sessions
            
        Returns:
            Transaction matrix (list of lists)
        """
        transactions = []
        
        for session_id, products in sessions.items():
            transactions.append(products)
        
        # Calculate average
        if transactions:
            total_products = sum(len(t) for t in transactions)
            self.stats['avg_products_per_session'] = total_products / len(transactions)
        
        return transactions
    
    def prepare_transactions(self, train_path: str) -> List[List[str]]:
        """
        Complete transaction preparation pipeline
        
        Args:
            train_path: Path to train.json
            
        Returns:
            Transaction matrix
        """
        print("Loading training data...")
        records = self.load_train_data(train_path)
        
        print("Grouping by session...")
        sessions = self.group_by_session(records)
        
        print("Filtering sessions...")
        filtered_sessions = self.filter_sessions(sessions)
        
        print("Creating transaction matrix...")
        transactions = self.create_transaction_matrix(filtered_sessions)
        
        print(f"✓ Transaction matrix created:")
        print(f"  - Total records: {self.stats['total_records']}")
        print(f"  - Total sessions: {self.stats['total_sessions']}")
        print(f"  - Filtered sessions: {self.stats['filtered_sessions']}")
        print(f"  - Avg products per session: {self.stats['avg_products_per_session']:.2f}")
        
        return transactions


class AprioriEngine:
    """
    Run Apriori algorithm to find association rules
    """
    
    def __init__(self, min_support: float = 0.015, min_confidence: float = 0.60,
                 min_lift: float = 1.5, max_len: int = 5):
        """
        Initialize Apriori engine
        
        Args:
            min_support: Minimum support threshold
            min_confidence: Minimum confidence threshold
            min_lift: Minimum lift threshold
            max_len: Maximum itemset length
        """
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.max_len = max_len
        
        self.frequent_itemsets = None
        self.rules = None
    
    def run_apriori(self, transactions: List[List[str]]) -> pd.DataFrame:
        """
        Run Apriori algorithm
        
        Args:
            transactions: Transaction matrix
            
        Returns:
            DataFrame of frequent itemsets
        """
        print(f"Running Apriori algorithm...")
        print(f"  - min_support: {self.min_support}")
        print(f"  - min_confidence: {self.min_confidence}")
        print(f"  - min_lift: {self.min_lift}")
        print(f"  - max_len: {self.max_len}")
        
        # Encode transactions (fallback if TransactionEncoder unavailable)
        try:
            te = TransactionEncoder()
            te_ary = te.fit(transactions).transform(transactions)
            df = pd.DataFrame(te_ary, columns=te.columns_)
        except Exception:
            # Manual one-hot encoding as a robust fallback
            all_items = sorted({item for txn in transactions for item in txn})
            df = pd.DataFrame(
                [[item in txn for item in all_items] for txn in transactions],
                columns=all_items,
                dtype=bool,
            )
        
        # Run Apriori
        self.frequent_itemsets = apriori(
            df, 
            min_support=self.min_support, 
            use_colnames=True,
            max_len=self.max_len
        )
        
        print(f"✓ Found {len(self.frequent_itemsets)} frequent itemsets")
        
        return self.frequent_itemsets
    
    def generate_association_rules(self) -> pd.DataFrame:
        """
        Generate association rules from frequent itemsets
        
        Returns:
            DataFrame of association rules
        """
        if self.frequent_itemsets is None:
            raise ValueError("Must run Apriori first")
        
        print("Generating association rules...")
        
        # Generate product-level association rules
        try:
            self.rules = association_rules(
                self.frequent_itemsets,
                metric="confidence",
                min_threshold=self.min_confidence
            )
            
            # Apply lift filtering for quality
            if len(self.rules) > 0:
                self.rules = self.rules[self.rules['lift'] >= self.min_lift]
                print(f"  After lift filtering (>={self.min_lift}): {len(self.rules)} rules")
        except ValueError as e:
            print(f"Warning: Could not generate rules - {e}")
            print("This usually means no frequent itemsets with 2+ items were found.")
            self.rules = None
            return None
        
        print(f"✓ Generated {len(self.rules)} association rules")
        
        return self.rules
    
    def export_rules_to_json(self) -> List[Dict[str, Any]]:
        """
        Export rules to JSON format
        
        Returns:
            List of rule dictionaries
        """
        if self.rules is None or len(self.rules) == 0:
            return []
        
        rules_list = []
        
        for idx, row in self.rules.iterrows():
            rule = {
                'antecedents': list(row['antecedents']),
                'consequents': list(row['consequents']),
                'support': float(row['support']),
                'confidence': float(row['confidence']),
                'lift': float(row['lift']),
                'antecedent_len': len(row['antecedents']),
                'consequent_len': len(row['consequents'])
            }
            rules_list.append(rule)
        
        return rules_list


class StatisticsCalculator:
    """
    Calculate normalization parameters from training data
    """
    
    @staticmethod
    def calculate_graph_stats(graph_structure: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate graph statistics"""
        nodes = graph_structure['nodes']
        
        if not nodes:
            return {}
        
        stats = {
            'max_in_degree': max(n['in_degree'] for n in nodes),
            'max_out_degree': max(n['out_degree'] for n in nodes),
            'max_pagerank': max(n['pagerank'] for n in nodes) if any(n['pagerank'] > 0 for n in nodes) else 1.0,
            'total_nodes': len(nodes),
            'total_edges': graph_structure['metadata']['total_edges']
        }
        
        return stats
    
    @staticmethod
    def calculate_session_stats(train_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate session statistics"""
        if not train_records:
            return {}
        
        durations = [r.get('session_duration_minutes', 0) for r in train_records]
        depths = [r.get('session_depth', 0) for r in train_records]
        positions = [r.get('click_position', 0) for r in train_records]
        
        stats = {
            'max_duration': max(durations) if durations else 1.0,
            'max_click_position': max(positions) if positions else 1,
            'max_session_depth': max(depths) if depths else 1,
            'avg_session_length': np.mean([len(r.get('previous_products', [])) for r in train_records])
        }
        
        return stats
    
    @staticmethod
    def calculate_category_stats(train_records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate category statistics"""
        category_data = defaultdict(lambda: {'count': 0, 'interest_sum': 0})
        
        for record in train_records:
            category = record.get('category')
            if category:
                category_data[category]['count'] += 1
                category_data[category]['interest_sum'] += record.get('interest', 0)
        
        category_stats = {}
        for category, data in category_data.items():
            category_stats[category] = {
                'count': data['count'],
                'avg_interest': data['interest_sum'] / max(data['count'], 1)
            }
        
        return category_stats
    
    @staticmethod
    def calculate_global_baseline(train_records: List[Dict[str, Any]]) -> float:
        """Calculate global interest baseline"""
        if not train_records:
            return 0.0
        
        interest_count = sum(1 for r in train_records if r.get('interest') == 1)
        return interest_count / len(train_records)


from custom_predictor import CustomPredictor, ModelTrainer


class Phase2Pipeline:
    """
    Complete Phase 2 pipeline: Apriori + Training
    """
    
    def __init__(self, config_path: str, train_path: str, output_dir: str):
        """
        Initialize Phase 2 pipeline
        
        Args:
            config_path: Path to config.yaml
            train_path: Path to train.json
            output_dir: Path to outputs directory
        """
        import yaml
        
        self.config_path = config_path
        self.train_path = train_path
        self.output_dir = output_dir
        
        # Load config
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # Extract Apriori parameters (use defaults if not in config)
        # STRATEGY: Product-level recommendations (serviceId specific)
        # Use relaxed parameters due to higher sparsity at product level
        self.min_support = 0.001  # 0.1% - accept rare product patterns
        self.min_confidence = 0.3  # 30% - reasonable confidence
        self.min_lift = 1.2  # Positive correlation
        self.max_len = 5
        
        print("Phase 2 Pipeline initialized!")
    
    def run_full_pipeline(self) -> None:
        """Run complete Phase 2 pipeline"""
        print("="*70)
        print("PHASE 2: APRIORI + TRAINING")
        print("="*70)
        
        start_time = datetime.now()
        
        # Step 2.1: Prepare Transactions
        print("\n=== STEP 2.1: TRANSACTION PREPARATION ===")
        transaction_builder = TransactionBuilder(min_products=2, max_products=20)  # Keep 2+ to ensure co-occurrence
        transactions = transaction_builder.prepare_transactions(self.train_path)
        
        if not transactions:
            print("ERROR: No transactions created. Exiting.")
            return
        
        # Step 2.2: Run Apriori Algorithm
        print("\n=== STEP 2.2: APRIORI ALGORITHM ===")
        apriori_engine = AprioriEngine(
            min_support=self.min_support,
            min_confidence=self.min_confidence,
            min_lift=self.min_lift,
            max_len=self.max_len
        )
        
        frequent_itemsets = apriori_engine.run_apriori(transactions)
        rules_df = apriori_engine.generate_association_rules()
        rules_list = apriori_engine.export_rules_to_json()
        
        if not rules_list:
            print("ERROR: No rules generated. Try lowering min_support or min_confidence.")
            return
        
        # Step 2.3: Load train records (no graph construction)
        print("\n=== STEP 2.3: LOADING TRAIN RECORDS ===")
        with open(self.train_path, 'r', encoding='utf-8') as f:
            train_records = json.load(f)

        graph_structure = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'total_nodes': 0,
                'total_edges': 0,
                'graph_density': 0
            }
        }

        # Step 2.4: Calculate Statistics
        print("\n=== STEP 2.4: STATISTICS CALCULATION ===")
        graph_stats = {}
        session_stats = StatisticsCalculator.calculate_session_stats(train_records)
        category_stats = StatisticsCalculator.calculate_category_stats(train_records)
        global_baseline = StatisticsCalculator.calculate_global_baseline(train_records)
        
        train_statistics = {
            'graph_stats': graph_stats,
            'session_stats': session_stats,
            'category_stats': category_stats,
            'global_baseline': global_baseline
        }
        
        print("✓ Statistics calculated:")
        print(f"  - Global baseline: {global_baseline:.4f}")
        
        # Step 2.5: Train Custom Predictor
        print("\n=== STEP 2.5: CUSTOM PREDICTOR TRAINING ===")
        trainer = ModelTrainer(rules_list, graph_structure, train_records)
        train_metrics = trainer.train_on_train_set()
        
        # Step 2.6: Save Model Artifacts
        print("\n=== STEP 2.6: SAVING MODEL ARTIFACTS ===")
        self._save_model_artifacts(
            rules_list, 
            graph_structure, 
            train_statistics, 
            train_metrics,
            trainer.predictor
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*70)
        print("PHASE 2 COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"Total training time: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"Output files saved to: {self.output_dir}")
    
    def _save_model_artifacts(self, rules: List[Dict[str, Any]],
                             graph: Dict[str, Any],
                             statistics: Dict[str, Any],
                             train_metrics: Dict[str, float],
                             predictor: CustomPredictor) -> None:
        """Save all model artifacts"""
        
        # Save rules.json
        rules_output = {
            'metadata': {
                'algorithm': 'apriori',
                'approach': 'product_level_recommendation',
                'granularity': 'product',  # serviceId level (not category)
                'min_support': self.min_support,
                'min_confidence': self.min_confidence,
                'min_lift': self.min_lift,
                'total_rules': len(rules),
                'total_products': len(graph['nodes']),
                'generated_at': datetime.now().isoformat()
            },
            'rules': rules
        }
        
        rules_path = os.path.join(self.output_dir, 'rules.json')
        with open(rules_path, 'w', encoding='utf-8') as f:
            json.dump(rules_output, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {rules_path}")
        
        # Save model_config.json
        model_config = {
            'version': '1.0',
            'prediction': {
                'method': 'custom_gradient_boosting',
                'weights': predictor.weights,
                'activation': 'sigmoid',
                'threshold': predictor.threshold
            },
            'normalization': statistics,
            'cold_start': {
                'strategy': 'global_baseline',
                'baseline_value': statistics['global_baseline']
            }
        }
        
        config_path = os.path.join(self.output_dir, 'model_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(model_config, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {config_path}")
        
        # Save train_statistics.json
        stats_path = os.path.join(self.output_dir, 'train_statistics.json')
        with open(stats_path, 'w', encoding='utf-8') as f:
            json.dump(statistics, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {stats_path}")
        
        # Save train_evaluation.json
        evaluation = {
            'metrics': train_metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        eval_path = os.path.join(self.output_dir, 'train_evaluation.json')
        with open(eval_path, 'w', encoding='utf-8') as f:
            json.dump(evaluation, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {eval_path}")


def main():
    """Main entry point"""
    config_path = '/Users/lab1/Documents/ACGI/config.yaml'
    train_path = '/Users/lab1/Documents/ACGI/outputs/train.json'
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    
    pipeline = Phase2Pipeline(config_path, train_path, output_dir)
    pipeline.run_full_pipeline()


if __name__ == '__main__':
    main()
