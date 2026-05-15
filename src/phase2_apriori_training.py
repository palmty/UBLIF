"""
Phase 2: Apriori + Training
Transaction preparation, Apriori algorithm, and custom prediction
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple, Set, Optional
from collections import defaultdict
from itertools import combinations
from tqdm import tqdm
import numpy as np

# Import mlxtend for Apriori
try:
    from mlxtend.frequent_patterns import apriori, association_rules
    from mlxtend.preprocessing import TransactionEncoder
except ImportError:
    print("WARNING: mlxtend not installed. Install with: pip install mlxtend")

# Import xgboost for ranking (optional)
try:
    import xgboost as xgb
except ImportError:
    xgb = None

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
        
        transactions = self.prepare_transactions_from_records(records)
        
        print(f"✓ Transaction matrix created:")
        print(f"  - Total records: {self.stats['total_records']}")
        print(f"  - Total sessions: {self.stats['total_sessions']}")
        print(f"  - Filtered sessions: {self.stats['filtered_sessions']}")
        print(f"  - Avg products per session: {self.stats['avg_products_per_session']:.2f}")
        
        return transactions

    def prepare_transactions_from_records(self, records: List[Dict[str, Any]]) -> List[List[str]]:
        """Prepare transactions from in-memory records"""
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


class IncrementalAprioriUpdater:
    """
    Incrementally update frequent itemsets and association rules
    """

    def __init__(self, min_support: float, min_confidence: float, min_lift: float, max_len: int):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.max_len = max_len

    @staticmethod
    def _itemset_key(itemset: Set[str]) -> str:
        return "|".join(sorted(itemset))

    def _load_old_rules(self, rules_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, int]]:
        if not os.path.exists(rules_path):
            return [], {}, {}

        with open(rules_path, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        old_rules = payload.get('rules', [])
        metadata = payload.get('metadata', {})
        support_counts = metadata.get('support_counts', {})

        if not support_counts and metadata.get('total_transactions'):
            total_txn = metadata.get('total_transactions')
            for rule in old_rules:
                itemset = set(rule.get('antecedents', [])) | set(rule.get('consequents', []))
                key = self._itemset_key(itemset)
                support_counts[key] = int(round(rule.get('support', 0.0) * total_txn))

        return old_rules, metadata, support_counts

    def _count_itemsets(self, transactions: List[List[str]], itemsets: List[Set[str]]) -> Dict[str, int]:
        counts = defaultdict(int)
        itemset_keys = [(self._itemset_key(itemset), itemset) for itemset in itemsets]
        for txn in transactions:
            txn_set = set(txn)
            for key, itemset in itemset_keys:
                if itemset.issubset(txn_set):
                    counts[key] += 1
        return counts

    def _generate_new_itemsets(self, transactions: List[List[str]], min_support_new: float) -> List[Set[str]]:
        if not transactions:
            return []

        try:
            te = TransactionEncoder()
            te_ary = te.fit(transactions).transform(transactions)
            df = pd.DataFrame(te_ary, columns=te.columns_)
        except Exception:
            all_items = sorted({item for txn in transactions for item in txn})
            df = pd.DataFrame(
                [[item in txn for item in all_items] for txn in transactions],
                columns=all_items,
                dtype=bool,
            )

        frequent_itemsets = apriori(
            df,
            min_support=min_support_new,
            use_colnames=True,
            max_len=self.max_len
        )

        return [set(items) for items in frequent_itemsets['itemsets'].tolist()]

    def update_rules(self, transactions_new: List[List[str]], rules_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        old_rules, metadata, old_counts = self._load_old_rules(rules_path)
        n_old = int(metadata.get('total_transactions', 0))
        n_new = len(transactions_new)
        total_txn = n_old + n_new

        if total_txn == 0:
            return [], {}

        old_itemsets = [set(r.get('antecedents', [])) | set(r.get('consequents', [])) for r in old_rules]
        new_counts = self._count_itemsets(transactions_new, old_itemsets)

        # New candidate generation using incremental threshold
        min_support_new = (self.min_support * total_txn) / max(n_new, 1)
        candidate_itemsets = self._generate_new_itemsets(transactions_new, min_support_new)
        candidate_counts = self._count_itemsets(transactions_new, candidate_itemsets)

        # Merge counts and prune
        merged_counts = {}
        for key, count_old in old_counts.items():
            count_new = new_counts.get(key, 0)
            merged_counts[key] = count_old + count_new

        for key, count_new in candidate_counts.items():
            merged_counts[key] = merged_counts.get(key, 0) + count_new

        # Ensure subset supports exist for association_rules
        missing_subset_keys = set()
        for key in list(merged_counts.keys()):
            if not key:
                continue
            items = key.split('|')
            if len(items) < 2:
                continue
            for r in range(1, len(items)):
                for subset in combinations(items, r):
                    subset_key = "|".join(subset)
                    if subset_key not in merged_counts:
                        missing_subset_keys.add(subset_key)

        if missing_subset_keys:
            subset_itemsets = [set(key.split('|')) for key in missing_subset_keys if key]
            subset_counts = self._count_itemsets(transactions_new, subset_itemsets)
            for subset_key, count_new in subset_counts.items():
                merged_counts[subset_key] = merged_counts.get(subset_key, 0) + count_new

        all_itemsets = []
        for key, count in merged_counts.items():
            items = set(key.split('|')) if key else set()
            all_itemsets.append({'itemsets': frozenset(items), 'support': count / total_txn})

        itemsets_df = pd.DataFrame(all_itemsets)
        if itemsets_df.empty:
            return [], {}

        rules_df = association_rules(
            itemsets_df,
            metric="confidence",
            min_threshold=self.min_confidence
        )
        if not rules_df.empty:
            rules_df['confidence'] = rules_df['confidence'].clip(lower=0, upper=1.0)
            rules_df['lift'] = rules_df['confidence'] / rules_df['consequent support']
        if not rules_df.empty:
            rules_df = rules_df[
                (rules_df['support'] >= self.min_support) &
                (rules_df['lift'] >= self.min_lift)
            ]

        rules_list = []
        for _, row in rules_df.iterrows():
            rule_itemset = set(row['antecedents']) | set(row['consequents'])
            key = self._itemset_key(rule_itemset)
            rules_list.append({
                'antecedents': list(row['antecedents']),
                'consequents': list(row['consequents']),
                'support': float(row['support']),
                'confidence': float(row['confidence']),
                'lift': float(row['lift']),
                'antecedent_len': len(row['antecedents']),
                'consequent_len': len(row['consequents']),
                'support_count': int(round(row['support'] * total_txn)),
                'itemset_key': key
            })

        updated_metadata = {
            'total_transactions': total_txn,
            'support_counts': merged_counts,
            'n_old': n_old,
            'n_new': n_new
        }

        return rules_list, updated_metadata


class XGBoostRuleRanker:
    """
    Rank rules by XGBoost gain using new session data
    """

    def __init__(self, min_gain: float = 0.0, max_rules: int = 5000):
        self.min_gain = min_gain
        self.max_rules = max_rules

    @staticmethod
    def _rule_itemset(rule: Dict[str, Any]) -> Set[str]:
        return set(rule.get('antecedents', [])) | set(rule.get('consequents', []))

    def _build_feature_matrix(
        self,
        transactions: List[List[str]],
        rules: List[Dict[str, Any]]
    ) -> Tuple[np.ndarray, List[str]]:
        rule_itemsets = [self._rule_itemset(rule) for rule in rules]
        feature_names = [f"rule_{i}" for i in range(len(rules))]

        x = np.zeros((len(transactions), len(feature_names)), dtype=float)
        for i, txn in enumerate(transactions):
            txn_set = set(txn)
            for j, itemset in enumerate(rule_itemsets):
                if itemset and itemset.issubset(txn_set):
                    x[i, j] = 1.0

        return x, feature_names

    def rank_rules(
        self,
        rules: List[Dict[str, Any]],
        transactions: List[List[str]],
        labels: List[int]
    ) -> List[Dict[str, Any]]:
        if not rules or not transactions:
            return rules

        if len(rules) > self.max_rules:
            rules = rules[:self.max_rules]

        x, feature_names = self._build_feature_matrix(transactions, rules)
        y = np.array(labels, dtype=float)

        if xgb is None:
            # Fallback: rank by support * confidence * lift
            scores = [r.get('support', 0.0) * r.get('confidence', 0.0) * r.get('lift', 0.0) for r in rules]
            ranked = sorted(range(len(rules)), key=lambda i: scores[i], reverse=True)
            for rank, idx in enumerate(ranked, start=1):
                rules[idx]['xgboost_gain'] = float(scores[idx])
                rules[idx]['importance_rank'] = rank
                rules[idx]['priority'] = 'high' if scores[idx] > 0 else 'low'
            return rules

        group = [len(y)]
        model = xgb.XGBRanker(
            objective='rank:pairwise',
            eval_metric='ndcg',
            learning_rate=0.1,
            max_depth=6,
            n_estimators=200,
            subsample=0.9,
            colsample_bytree=0.8,
            tree_method='hist'
        )
        model.fit(x, y, group=group)

        booster = model.get_booster()
        gain_scores = booster.get_score(importance_type='gain')

        rule_gains = []
        for i in range(len(rules)):
            key = f"f{i}"
            rule_gains.append(float(gain_scores.get(key, 0.0)))

        ranked = sorted(range(len(rules)), key=lambda i: rule_gains[i], reverse=True)
        for rank, idx in enumerate(ranked, start=1):
            gain = rule_gains[idx]
            rules[idx]['xgboost_gain'] = gain
            rules[idx]['importance_rank'] = rank
            rules[idx]['priority'] = 'high' if gain > self.min_gain else 'low'

        return rules


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

    @staticmethod
    def rank_rules_with_xgboost(
        rules: List[Dict[str, Any]],
        train_records: List[Dict[str, Any]],
        session_stats: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank rules by XGBoost feature importance using session-level records.

        Args:
            rules: List of rule dicts from Apriori.
            train_records: List of training records.
            session_stats: Optional session stats (not required for ranking).

        Returns:
            Ranked rules with xgboost_gain and sorted descending.
        """
        if not rules or not train_records:
            return rules

        if xgb is None:
            # Fallback: rank by support * confidence * lift
            scores = [r.get('support', 0.0) * r.get('confidence', 0.0) * r.get('lift', 0.0) for r in rules]
            ranked = sorted(range(len(rules)), key=lambda i: scores[i], reverse=True)
            for rank, idx in enumerate(ranked, start=1):
                rules[idx]['xgboost_gain'] = float(scores[idx])
                rules[idx]['importance_rank'] = rank
            return rules

        rule_features = []
        labels = []

        for record in train_records:
            prev_items = set(record.get('previous_products', []))
            row = []
            for rule in rules:
                antecedents = set(rule.get('antecedents', []))
                is_match = 1 if antecedents.issubset(prev_items) else 0
                row.append(is_match)

            rule_features.append(row)
            labels.append(record.get('interest', 0))

        x = pd.DataFrame(rule_features)
        y = np.array(labels)

        ranker = xgb.XGBClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            objective='binary:logistic'
        )
        ranker.fit(x, y)

        importances = ranker.feature_importances_

        for i, rule in enumerate(rules):
            rule['xgboost_gain'] = float(importances[i])

        ranked_rules = [r for r in rules if r.get('xgboost_gain', 0.0) > 0]
        ranked_rules.sort(key=lambda x: x['xgboost_gain'], reverse=True)

        for rank, rule in enumerate(ranked_rules, start=1):
            rule['importance_rank'] = rank

        return ranked_rules


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
    
    def _build_sessions_with_features(self, records: List[Dict[str, Any]], min_products: int, max_products: int) -> Tuple[List[List[str]], List[Dict[str, float]], List[int]]:
        sessions = defaultdict(list)
        session_features = defaultdict(lambda: defaultdict(list))
        session_labels = defaultdict(int)

        for record in records:
            session_id = record.get('session_id')
            product_id = record.get('product_id')
            if not session_id or not product_id:
                continue

            sessions[session_id].append(str(product_id))

            session_features[session_id]['session_duration'].append(record.get('session_duration_minutes', 0.0))
            session_features[session_id]['bounce_penalty'].append(record.get('bounce_penalty', 0.0))
            session_features[session_id]['session_depth'].append(record.get('session_depth', 0.0))
            session_features[session_id]['click_position'].append(record.get('click_position', 0.0))
            session_labels[session_id] = max(session_labels[session_id], int(record.get('interest', 0)))

        transactions = []
        features = []
        labels = []

        for session_id, products in sessions.items():
            unique_products = list(dict.fromkeys(products))
            if min_products <= len(unique_products) <= max_products:
                transactions.append(unique_products)
                feats = session_features[session_id]
                features.append({
                    'session_duration': float(np.mean(feats['session_duration'])) if feats['session_duration'] else 0.0,
                    'bounce_penalty': float(np.mean(feats['bounce_penalty'])) if feats['bounce_penalty'] else 0.0,
                    'session_depth': float(np.mean(feats['session_depth'])) if feats['session_depth'] else 0.0,
                    'click_position': float(np.mean(feats['click_position'])) if feats['click_position'] else 0.0,
                    'session_length': float(len(unique_products))
                })
                labels.append(session_labels[session_id])

        return transactions, features, labels

    def run_full_pipeline(self) -> None:
        """Run complete Phase 2 pipeline"""
        print("="*70)
        print("PHASE 2: APRIORI + TRAINING")
        print("="*70)
        
        start_time = datetime.now()
        
        # Step 2.1: Load records + Prepare Transactions
        print("\n=== STEP 2.1: TRANSACTION PREPARATION ===")
        transaction_builder = TransactionBuilder(min_products=2, max_products=20)  # Keep 2+ to ensure co-occurrence
        with open(self.train_path, 'r', encoding='utf-8') as f:
            train_records = json.load(f)
        transaction_builder.stats['total_records'] = len(train_records)
        transactions = transaction_builder.prepare_transactions_from_records(train_records)

        transactions_new, session_features, labels_new = self._build_sessions_with_features(
            train_records,
            transaction_builder.min_products,
            transaction_builder.max_products
        )
        
        if not transactions:
            print("ERROR: No transactions created. Exiting.")
            return
        
        # Step 2.2: Incremental Apriori + Update Knowledge Base
        print("\n=== STEP 2.2: INCREMENTAL APRIORI UPDATE ===")
        rules_path = os.path.join(self.output_dir, 'rules.json')
        updater = IncrementalAprioriUpdater(
            min_support=self.min_support,
            min_confidence=self.min_confidence,
            min_lift=self.min_lift,
            max_len=self.max_len
        )
        rules_list, rules_metadata = updater.update_rules(transactions_new, rules_path)
        
        if not rules_list:
            print("ERROR: No rules generated. Try lowering min_support or min_confidence.")
            return
        
        # Step 2.3: Ranking & Pruning via XGBoost
        print("\n=== STEP 2.3: XGBOOST RANKING ===")
        ranker = XGBoostRuleRanker(min_gain=0.0, max_rules=5000)
        rules_list = ranker.rank_rules(rules_list, transactions_new, labels_new)

        # Step 2.4: Load train records (no graph construction)
        print("\n=== STEP 2.4: LOADING TRAIN RECORDS ===")
        graph_structure = {
            'nodes': [],
            'edges': [],
            'metadata': {
                'total_nodes': 0,
                'total_edges': 0,
                'graph_density': 0
            }
        }

        # Step 2.5: Calculate Statistics
        print("\n=== STEP 2.5: STATISTICS CALCULATION ===")
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
        
        # Step 2.6: Train Custom Predictor
        print("\n=== STEP 2.6: CUSTOM PREDICTOR TRAINING ===")
        trainer = ModelTrainer(rules_list, graph_structure, train_records)
        train_metrics = trainer.train_on_train_set()
        
        # Step 2.7: Save Model Artifacts
        print("\n=== STEP 2.7: SAVING MODEL ARTIFACTS ===")
        self._save_model_artifacts(
            rules_list, 
            graph_structure, 
            train_statistics, 
            train_metrics,
            trainer.predictor,
            rules_metadata
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
                             predictor: CustomPredictor,
                             rules_metadata: Optional[Dict[str, Any]] = None) -> None:
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
                'generated_at': datetime.now().isoformat(),
                'ranking_method': 'xgboost_ranker' if xgb is not None else 'heuristic_fallback'
            },
            'rules': rules
        }

        if rules_metadata:
            rules_output['metadata'].update(rules_metadata)
        
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
