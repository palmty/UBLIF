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

    def __init__(
        self,
        min_support: float,
        min_confidence: float,
        min_lift: float,
        max_len: int,
        border_ratio: float = 0.7,
        sliding_window_days: int = 30,
        new_item_ratio_multiplier: float = 2.0,
        new_item_ratio_floor: float = 0.01,
        dense_matrix_max_cells: int = 50000000
    ):
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.min_lift = min_lift
        self.max_len = max_len
        self.border_ratio = border_ratio
        self.sliding_window_days = sliding_window_days
        self.new_item_ratio_multiplier = new_item_ratio_multiplier
        self.new_item_ratio_floor = new_item_ratio_floor
        self.dense_matrix_max_cells = dense_matrix_max_cells

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

    @staticmethod
    def _count_singletons(transactions: List[List[str]]) -> Dict[str, int]:
        counts = defaultdict(int)
        for txn in transactions:
            for item in set(txn):
                counts[str(item)] += 1
        return counts

    @staticmethod
    def _extract_known_items(
        metadata: Dict[str, Any],
        old_rules: List[Dict[str, Any]],
        old_counts: Dict[str, int]
    ) -> Set[str]:
        known_items = set(metadata.get('known_items', []))
        if not known_items and old_counts:
            for key in old_counts.keys():
                for item in key.split('|'):
                    if item:
                        known_items.add(item)
        if not known_items and old_rules:
            for rule in old_rules:
                known_items.update(rule.get('antecedents', []))
                known_items.update(rule.get('consequents', []))
        return known_items

    def _compute_window_stats(self, transaction_timestamps: Optional[List[int]]) -> Dict[str, Any]:
        if not transaction_timestamps:
            return {}

        timestamps = [int(ts) for ts in transaction_timestamps if ts]
        if not timestamps:
            return {}

        window_seconds = int(self.sliding_window_days * 86400)
        window_end = max(timestamps)
        window_start = window_end - window_seconds
        window_txn = sum(1 for ts in timestamps if ts >= window_start)

        return {
            'window_seconds': window_seconds,
            'window_start': window_start,
            'window_end': window_end,
            'window_txn': window_txn
        }

    def _generate_new_itemsets_via_counts(
        self,
        transactions: List[List[str]],
        min_support_new: float
    ) -> List[Set[str]]:
        n_txn = len(transactions)
        if n_txn == 0:
            return []

        min_count = max(int(np.ceil(min_support_new * n_txn)), 1)
        singleton_counts = self._count_singletons(transactions)
        frequent_items = [item for item, count in singleton_counts.items() if count >= min_count]
        if not frequent_items:
            return []

        frequent_itemsets = [{item} for item in frequent_items]
        if self.max_len < 2:
            return frequent_itemsets

        frequent_items_set = set(frequent_items)
        for k in range(2, self.max_len + 1):
            counts = defaultdict(int)
            for txn in transactions:
                filtered = [item for item in set(txn) if item in frequent_items_set]
                if len(filtered) < k:
                    continue
                for combo in combinations(sorted(filtered), k):
                    counts[combo] += 1
            level_itemsets = [set(combo) for combo, count in counts.items() if count >= min_count]
            if not level_itemsets:
                break
            frequent_itemsets.extend(level_itemsets)

        return frequent_itemsets

    def detect_frequent_new_items(self, transactions_new: List[List[str]], rules_path: str) -> List[str]:
        old_rules, metadata, old_counts = self._load_old_rules(rules_path)
        if not old_rules and not old_counts and not metadata:
            return []

        known_items = self._extract_known_items(metadata, old_rules, old_counts)
        singleton_counts = self._count_singletons(transactions_new)
        n_new = len(transactions_new)
        if n_new == 0:
            return []

        new_items = [item for item in singleton_counts.keys() if item not in known_items]
        new_item_threshold = max(self.min_support * self.new_item_ratio_multiplier, self.new_item_ratio_floor)

        frequent_new_items = [
            item for item in new_items
            if (singleton_counts.get(item, 0) / n_new) >= new_item_threshold
        ]

        return frequent_new_items

    def _generate_new_itemsets(self, transactions: List[List[str]], min_support_new: float) -> List[Set[str]]:
        if not transactions:
            return []

        n_txn = len(transactions)
        unique_items = {item for txn in transactions for item in txn}
        n_items = len(unique_items)
        combo_factor = min(self.max_len, 3)
        if n_txn * n_items * combo_factor > self.dense_matrix_max_cells:
            return self._generate_new_itemsets_via_counts(transactions, min_support_new)

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
            max_len=self.max_len,
            low_memory=True
        )

        return [set(items) for items in frequent_itemsets['itemsets'].tolist()]

    def update_rules(
        self,
        transactions_new: List[List[str]],
        rules_path: str,
        transaction_timestamps: Optional[List[int]] = None,
        transactions_history: Optional[List[List[str]]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        old_rules, metadata, old_counts = self._load_old_rules(rules_path)
        incremental_round = int(metadata.get('incremental_round', 0)) + 1
        old_rule_keys = set()
        for rule in old_rules:
            rule_itemset = set(rule.get('antecedents', [])) | set(rule.get('consequents', []))
            key = self._itemset_key(rule_itemset)
            if key:
                old_rule_keys.add(key)
        n_old = int(metadata.get('total_transactions', 0))
        n_new = len(transactions_new)
        total_txn = n_old + n_new

        if total_txn == 0:
            return [], {}

        old_itemsets = [set(r.get('antecedents', [])) | set(r.get('consequents', [])) for r in old_rules]
        new_counts = self._count_itemsets(transactions_new, old_itemsets)

        known_items = self._extract_known_items(metadata, old_rules, old_counts)
        singleton_counts = self._count_singletons(transactions_new)
        new_items = [item for item in singleton_counts.keys() if item not in known_items]
        new_item_threshold = max(self.min_support * self.new_item_ratio_multiplier, self.new_item_ratio_floor)
        frequent_new_items = [
            item for item in new_items
            if (singleton_counts.get(item, 0) / max(n_new, 1)) >= new_item_threshold
        ]

        window_stats = self._compute_window_stats(transaction_timestamps)
        if window_stats:
            min_support_new = (self.min_support * max(window_stats['window_txn'], 1)) / max(n_new, 1)
            min_support_strategy = 'sliding_window'
        else:
            min_support_new = (self.min_support * total_txn) / max(n_new, 1)
            min_support_strategy = 'total_txn_scaled'

        min_support_new = min(max(min_support_new, 0.0), 1.0)
        min_support_border_new = min_support_new * self.border_ratio

        candidate_itemsets = self._generate_new_itemsets(transactions_new, min_support_new)
        border_candidate_itemsets = []
        if min_support_border_new < min_support_new:
            border_candidate_itemsets = self._generate_new_itemsets(transactions_new, min_support_border_new)

        if frequent_new_items:
            border_candidate_itemsets.extend([{item} for item in frequent_new_items])

        combined_itemsets = {}
        for itemset in candidate_itemsets + border_candidate_itemsets:
            combined_itemsets[frozenset(itemset)] = set(itemset)
        candidate_itemsets = list(combined_itemsets.values())

        candidate_counts = self._count_itemsets(transactions_new, candidate_itemsets)

        # Merge counts and prune
        merged_counts = {}
        for key, count_old in old_counts.items():
            count_new = new_counts.get(key, 0)
            merged_counts[key] = count_old + count_new

        for key, count_new in candidate_counts.items():
            merged_counts[key] = merged_counts.get(key, 0) + count_new

        selective_scan_applied = False
        selective_scan_needed = bool(frequent_new_items) and not transactions_history
        selective_scan_items = []
        selective_scan_history_txn = 0
        if frequent_new_items and transactions_history:
            frequent_set = set(frequent_new_items)
            scan_itemsets = [itemset for itemset in candidate_itemsets if itemset & frequent_set]
            if scan_itemsets:
                history_transactions = [
                    txn for txn in transactions_history
                    if frequent_set.intersection(txn)
                ]
                selective_scan_history_txn = len(history_transactions)
                history_counts = self._count_itemsets(history_transactions, scan_itemsets)
                for key, count_old in history_counts.items():
                    merged_counts[key] = merged_counts.get(key, 0) + count_old
                selective_scan_applied = True
                selective_scan_items = frequent_new_items

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

        old_border_support_counts = metadata.get('border_support_counts', {})
        border_total_prev = len(old_border_support_counts) if isinstance(old_border_support_counts, dict) else 0
        border_crossed_keys = []
        if border_total_prev:
            for key in old_border_support_counts.keys():
                support = merged_counts.get(key, 0) / total_txn
                if support >= self.min_support:
                    border_crossed_keys.append(key)

        border_lower = self.border_ratio * self.min_support
        border_support_counts = {}
        for key, count in merged_counts.items():
            support = count / total_txn
            if border_lower <= support < self.min_support:
                border_support_counts[key] = count

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
        rule_birth_rounds = metadata.get('rule_birth_rounds', {})
        if not isinstance(rule_birth_rounds, dict):
            rule_birth_rounds = {}
        rule_birth_rounds_next = {}
        for _, row in rules_df.iterrows():
            rule_itemset = set(row['antecedents']) | set(row['consequents'])
            key = self._itemset_key(rule_itemset)
            birth_round = int(rule_birth_rounds.get(key, incremental_round))
            rule_birth_rounds_next[key] = birth_round
            rule_age_rounds = max(incremental_round - birth_round + 1, 1)
            support_count_prev = int(old_counts.get(key, 0))
            support_count_now = int(round(row['support'] * total_txn))
            support_momentum = (support_count_now - support_count_prev) / max(support_count_prev, 1)
            rules_list.append({
                'antecedents': list(row['antecedents']),
                'consequents': list(row['consequents']),
                'support': float(row['support']),
                'confidence': float(row['confidence']),
                'lift': float(row['lift']),
                'antecedent_len': len(row['antecedents']),
                'consequent_len': len(row['consequents']),
                'support_count': support_count_now,
                'support_count_prev': support_count_prev,
                'support_momentum': float(support_momentum),
                'itemset_key': key,
                'rule_birth_round': birth_round,
                'rule_age_rounds': rule_age_rounds
            })

        new_rule_keys = {rule['itemset_key'] for rule in rules_list if rule.get('itemset_key')}
        if old_rule_keys:
            rule_change_ratio = (len(new_rule_keys - old_rule_keys) + len(old_rule_keys - new_rule_keys)) / max(len(old_rule_keys), 1)
        else:
            rule_change_ratio = 1.0 if new_rule_keys else 0.0

        updated_metadata = {
            'total_transactions': total_txn,
            'support_counts': merged_counts,
            'border_support_counts': border_support_counts,
            'border_ratio': self.border_ratio,
            'border_support_lower': border_lower,
            'min_support_strategy': min_support_strategy,
            'min_support_new': min_support_new,
            'min_support': self.min_support,
            'incremental_round': incremental_round,
            'rule_birth_rounds': rule_birth_rounds_next,
            'rule_change_ratio': rule_change_ratio,
            'n_old': n_old,
            'n_new': n_new,
            'known_items': sorted({item for key in merged_counts.keys() for item in key.split('|') if item}),
            'new_items_detected': sorted(new_items),
            'frequent_new_items': sorted(frequent_new_items),
            'new_item_threshold': new_item_threshold,
            'selective_scan_applied': selective_scan_applied,
            'selective_scan_needed': selective_scan_needed,
            'selective_scan_items': sorted(selective_scan_items),
            'selective_scan_history_txn': selective_scan_history_txn,
            'border_total_prev': border_total_prev,
            'border_crossed_count': len(border_crossed_keys)
        }

        if window_stats:
            updated_metadata.update(window_stats)

        return rules_list, updated_metadata


class XGBoostRuleRanker:
    """
    Rank rules by XGBoost gain using rule property features
    """

    def __init__(self, min_gain: float = 0.0, max_rules: int = 5000):
        self.min_gain = min_gain
        self.max_rules = max_rules

    @staticmethod
    def _rule_itemset(rule: Dict[str, Any]) -> Set[str]:
        return set(rule.get('antecedents', [])) | set(rule.get('consequents', []))

    def _build_rule_property_matrix(
        self,
        transactions: List[List[str]],
        rules: List[Dict[str, Any]],
        labels: List[float]
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, float]]]:
        rule_itemsets = [self._rule_itemset(rule) for rule in rules]
        match_counts = [0] * len(rules)
        label_sums = [0.0] * len(rules)
        label_sq_sums = [0.0] * len(rules)

        for txn, label in zip(transactions, labels):
            txn_set = set(txn)
            for i, itemset in enumerate(rule_itemsets):
                if itemset and itemset.issubset(txn_set):
                    match_counts[i] += 1
                    label_sums[i] += float(label)
                    label_sq_sums[i] += float(label) ** 2

        n_txn = len(transactions)
        features = []
        targets = []
        stats = []

        for i, rule in enumerate(rules):
            match_count = match_counts[i]
            match_rate = match_count / max(n_txn, 1)
            match_label_mean = label_sums[i] / max(match_count, 1)
            label_variance = 0.0
            if match_count > 1:
                label_variance = (label_sq_sums[i] / match_count) - (match_label_mean ** 2)
                if label_variance < 0:
                    label_variance = 0.0
            match_miss_count = n_txn - match_count

            stats.append({
                'match_count': float(match_count),
                'match_rate': float(match_rate),
                'match_label_mean': float(match_label_mean),
                'label_variance': float(label_variance),
                'match_miss_count': float(match_miss_count)
            })

            features.append([
                float(rule.get('support', 0.0)),
                float(rule.get('confidence', 0.0)),
                float(rule.get('lift', 0.0)),
                float(rule.get('support_count', 0)),
                float(rule.get('support_momentum', 0.0)),
                float(rule.get('antecedent_len', 0)),
                float(rule.get('consequent_len', 0)),
                float(rule.get('rule_age_rounds', 1)),
                float(match_rate),
                float(match_miss_count),
                float(label_variance)
            ])
            targets.append(match_label_mean)

        return np.array(features, dtype=float), np.array(targets, dtype=float), stats

    def rank_rules(
        self,
        rules: List[Dict[str, Any]],
        transactions: List[List[str]],
        labels: List[float]
    ) -> List[Dict[str, Any]]:
        if not rules or not transactions:
            return rules

        if len(rules) > self.max_rules:
            rules = rules[:self.max_rules]

        x, y, stats = self._build_rule_property_matrix(transactions, rules, labels)

        if x.size > 0:
            stats_cols = slice(0, 3)
            means = x[:, stats_cols].mean(axis=0)
            stds = x[:, stats_cols].std(axis=0)
            stds[stds == 0] = 1.0
            x[:, stats_cols] = (x[:, stats_cols] - means) / stds

        nonzero_targets = y[y > 0]
        if nonzero_targets.size > 0:
            match_label_threshold = float(np.quantile(nonzero_targets, 0.75))
        else:
            match_label_threshold = 0.0
        y_class = np.zeros_like(y, dtype=int)
        if match_label_threshold > 0:
            y_class[y >= match_label_threshold] = 1
        else:
            y_class[y > 0] = 1

        if xgb is None or len(np.unique(y_class)) < 2:
            scores = []
            for i, rule in enumerate(rules):
                match_rate = stats[i]['match_rate']
                match_label_mean = stats[i]['match_label_mean']
                score = match_label_mean * match_rate * rule.get('confidence', 0.0) * rule.get('lift', 0.0)
                scores.append(float(score))
        else:
            model = xgb.XGBClassifier(
                objective='binary:logistic',
                eval_metric='auc',
                learning_rate=0.1,
                max_depth=6,
                n_estimators=200,
                subsample=0.9,
                colsample_bytree=0.8,
                tree_method='hist'
            )
            if len(y_class) >= 20:
                rng = np.random.RandomState(42)
                indices = rng.permutation(len(y_class))
                split = int(len(indices) * 0.8)
                train_idx = indices[:split]
                val_idx = indices[split:]
                try:
                    model.fit(
                        x[train_idx],
                        y_class[train_idx],
                        eval_set=[(x[val_idx], y_class[val_idx])],
                        early_stopping_rounds=20,
                        verbose=False
                    )
                except TypeError:
                    model.fit(
                        x[train_idx],
                        y_class[train_idx],
                        eval_set=[(x[val_idx], y_class[val_idx])],
                        verbose=False
                    )
            else:
                model.fit(x, y_class)
            scores = [float(pred) for pred in model.predict_proba(x)[:, 1]]

        ranked = sorted(range(len(rules)), key=lambda i: scores[i], reverse=True)
        for rank, idx in enumerate(ranked, start=1):
            gain = scores[idx]
            rules[idx]['xgboost_gain'] = gain
            rules[idx]['importance_rank'] = rank
            rules[idx]['priority'] = 'high' if gain > self.min_gain else 'low'
            rules[idx]['match_count'] = int(stats[idx]['match_count'])
            rules[idx]['match_rate'] = float(stats[idx]['match_rate'])
            rules[idx]['match_label_mean'] = float(stats[idx]['match_label_mean'])
            rules[idx]['match_miss_count'] = int(stats[idx]['match_miss_count'])
            rules[idx]['label_variance'] = float(stats[idx]['label_variance'])

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

        transactions = [list(dict.fromkeys(record.get('previous_products', []))) for record in train_records]
        labels = [float(record.get('interest', 0)) for record in train_records]

        ranker = XGBoostRuleRanker(min_gain=0.0, max_rules=len(rules))
        return ranker.rank_rules(rules, transactions, labels)


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

        apriori_config = config.get('apriori', {}) if isinstance(config, dict) else {}
        self.apriori_history_path = apriori_config.get('history_path')

        labeling_config = config.get('labeling', {}) if isinstance(config, dict) else {}
        self.label_weights = labeling_config.get(
            'weights',
            {'click': 1.0, 'add_to_cart': 2.0, 'purchase': 3.0}
        )
        self.label_event_map = labeling_config.get(
            'event_type_map',
            {
                'purchase': ['purchase', 'order', 'checkout', 'paid'],
                'add_to_cart': ['add_to_cart', 'addtocart', 'cart', 'basket'],
                'click': ['click']
            }
        )
        self.label_source_field = labeling_config.get('source_field', 'event_type')
        
        # Extract Apriori parameters (use defaults if not in config)
        # STRATEGY: Product-level recommendations (serviceId specific)
        # Use relaxed parameters due to higher sparsity at product level
        self.min_support = 0.001  # 0.1% - accept rare product patterns
        self.min_confidence = 0.3  # 30% - reasonable confidence
        self.min_lift = 1.2  # Positive correlation
        self.max_len = 5
        
        print("Phase 2 Pipeline initialized!")
    
    def _build_sessions_with_features(
        self,
        records: List[Dict[str, Any]],
        min_products: int,
        max_products: int
    ) -> Tuple[List[List[str]], List[Dict[str, float]], List[float], List[int]]:
        sessions = defaultdict(list)
        session_features = defaultdict(lambda: defaultdict(list))
        session_labels = defaultdict(float)
        session_timestamps = defaultdict(list)

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
            session_labels[session_id] = max(
                session_labels[session_id],
                self._derive_label_weight(record)
            )
            session_timestamps[session_id].append(int(record.get('timestamp', 0) or 0))

        transactions = []
        features = []
        labels = []
        timestamps = []

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
                timestamps.append(max(session_timestamps[session_id]) if session_timestamps[session_id] else 0)

        return transactions, features, labels, timestamps

    def _derive_label_weight(self, record: Dict[str, Any]) -> float:
        event_value = str(record.get(self.label_source_field, '')).lower()
        for label_key, patterns in self.label_event_map.items():
            for pattern in patterns:
                if pattern and pattern in event_value:
                    return float(self.label_weights.get(label_key, 0.0))
        return 0.0

    def _build_history_transactions_for_items(
        self,
        records: List[Dict[str, Any]],
        items: Set[str],
        min_products: int,
        max_products: int
    ) -> List[List[str]]:
        if not items:
            return []

        builder = TransactionBuilder(min_products=min_products, max_products=max_products)
        sessions = builder.group_by_session(records)
        filtered_sessions = {
            session_id: products
            for session_id, products in sessions.items()
            if items.intersection(products)
        }
        filtered_sessions = builder.filter_sessions(filtered_sessions)
        return builder.create_transaction_matrix(filtered_sessions)

    def _append_training_log(self, rules_metadata: Optional[Dict[str, Any]]) -> None:
        if not rules_metadata:
            return

        log_path = os.path.join(self.output_dir, 'training_log.txt')
        timestamp = datetime.now().isoformat()
        selective_scan_applied = int(bool(rules_metadata.get('selective_scan_applied')))
        selective_scan_history_txn = int(rules_metadata.get('selective_scan_history_txn', 0))
        border_total_prev = int(rules_metadata.get('border_total_prev', 0))
        border_crossed = int(rules_metadata.get('border_crossed_count', 0))
        border_crossed_ratio = border_crossed / max(border_total_prev, 1)
        border_total_now = len(rules_metadata.get('border_support_counts', {}))
        n_new = int(rules_metadata.get('n_new', 0))
        min_support_strategy = rules_metadata.get('min_support_strategy', 'unknown')
        min_support_new = rules_metadata.get('min_support_new', 0.0)
        min_support = rules_metadata.get('min_support', self.min_support)

        log_line = (
            f"{timestamp}\t"
            f"n_new={n_new}\t"
            f"selective_scan={selective_scan_applied}\t"
            f"selective_scan_history_txn={selective_scan_history_txn}\t"
            f"border_prev={border_total_prev}\t"
            f"border_crossed={border_crossed}\t"
            f"border_crossed_ratio={border_crossed_ratio:.4f}\t"
            f"border_now={border_total_now}\t"
            f"min_support={min_support}\t"
            f"min_support_new={min_support_new:.6f}\t"
            f"min_support_strategy={min_support_strategy}"
        )

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")

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

        transactions_new, session_features, labels_new, session_timestamps = self._build_sessions_with_features(
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

        transactions_history = None
        if self.apriori_history_path:
            try:
                history_path = os.path.abspath(self.apriori_history_path)
                train_path = os.path.abspath(self.train_path)
            except Exception:
                history_path = self.apriori_history_path
                train_path = self.train_path

            if os.path.exists(history_path) and history_path != train_path:
                frequent_new_items = updater.detect_frequent_new_items(transactions_new, rules_path)
                if frequent_new_items:
                    with open(history_path, 'r', encoding='utf-8') as f:
                        history_records = json.load(f)
                    transactions_history = self._build_history_transactions_for_items(
                        history_records,
                        set(frequent_new_items),
                        transaction_builder.min_products,
                        transaction_builder.max_products
                    )

        rules_list, rules_metadata = updater.update_rules(
            transactions_new,
            rules_path,
            transaction_timestamps=session_timestamps,
            transactions_history=transactions_history
        )

        if rules_metadata is not None:
            rules_metadata.update({
                'label_strategy': 'event_type_weighted',
                'label_source_field': self.label_source_field,
                'label_weights': self.label_weights,
                'label_event_map': self.label_event_map
            })

        self._append_training_log(rules_metadata)
        
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
