"""
Custom Predictor Module
Implements custom gradient boosting-like prediction formula
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score


class CustomPredictor:
    """
    Custom prediction formula combining:
    - Tree 1: Rule Matching
    - Tree 2: Enhanced Session Features with Negative Scoring
    
    Enhanced session features with penalty system:
    - Session duration and click position (positive factors)
    - Time features with penalty (off-peak hours = negative)
    - Location features with penalty (outside target zone = negative)
    - Behavioral features (category views = positive)
    - Score range: [-1, 1] allowing penalties for suboptimal conditions
    """
    
    def __init__(self, rules: List[Dict[str, Any]],
                 graph_structure: Dict[str, Any],
                 statistics: Dict[str, Any]):
        """
        Initialize predictor
        
        Args:
            rules: Association rules
            graph_structure: Placeholder structure (unused)
            statistics: Normalization statistics
        """
        self.rules = rules
        self.stats = statistics
        
        # Create rule lookup by consequents
        self.rule_lookup = self._create_rule_lookup()
        
        # Weights for ensemble (tuned on train set)
        self.weights = {
            'rule_matching': 0.7,
            'session_features': 0.3
        }
        
        self.threshold = 0.45  # Decision threshold on probability
        self.rule_lift_threshold = 1.2
        self.sigmoid_scale = 6.0

        # Session feature tuning knobs
        self.penalty_low_depth = 0.1
        self.penalty_short_duration = 0.1
        self.bonus_scale = 0.3

        gains = [r.get('xgboost_gain', 0.0) for r in self.rules]
        self.gain_min = min(gains) if gains else 0.0
        self.gain_max = max(gains) if gains else 0.0

    def _normalize_gain(self, gain: float) -> float:
        if self.gain_max <= self.gain_min:
            return 0.0
        normalized = (gain - self.gain_min) / (self.gain_max - self.gain_min)
        return normalized * 1.5
    
    def _create_rule_lookup(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create lookup dictionary for rules by consequent"""
        lookup = {}
        
        for rule in self.rules:
            for cons in rule['consequents']:
                if cons not in lookup:
                    lookup[cons] = []
                lookup[cons].append(rule)
        
        return lookup
    
    def find_best_rule(self, previous_products: List[str], 
                      product_id: str) -> Optional[Dict[str, Any]]:
        """
        Find best matching rule for product given previous products
        
        Args:
            previous_products: List of previous product IDs
            product_id: Target product ID
            
        Returns:
            Best matching rule or None
        """
        if not previous_products or product_id not in self.rule_lookup:
            return None
        
        prev_set = set(previous_products)
        best_rule = None
        best_score = 0
        
        # Find rules with this product as consequent
        candidate_rules = self.rule_lookup.get(product_id, [])
        
        for rule in candidate_rules:
            # Normalize gain to create wider gaps between rules
            rule_gain = self._normalize_gain(rule.get('xgboost_gain', 0.0))
            antecedents_set = set(rule['antecedents'])
            
            # Calculate overlap
            overlap = len(prev_set.intersection(antecedents_set))
            
            if overlap > 0:
                # Gain-based score to prioritize predictive rules
                score = overlap * (1 + rule_gain)
                
                if score > best_score:
                    best_score = score
                    best_rule = rule
        
        return best_rule
    
    def calculate_rule_matching_score(self, record: Dict[str, Any]) -> float:
        """
        Calculate Tree 1: Rule Matching score
        
        Args:
            record: Record to score
            
        Returns:
            Rule matching score [0, 1]
        """
        previous_products = record.get('previous_products', [])
        product_id = str(record.get('product_id', ''))
        
        matched_rule = self.find_best_rule(previous_products, product_id)

        if not matched_rule:
            return 0.0

        lift = matched_rule.get('lift', 0.0)
        conf = matched_rule.get('confidence', 0.0)
        gain = self._normalize_gain(matched_rule.get('xgboost_gain', 0.0))

        lift_weight = min(lift / max(self.rule_lift_threshold, 1e-6), 1.5)
        return conf * (1.0 + gain) * lift_weight
    
    def calculate_session_features_score(self, record: Dict[str, Any]) -> float:
        """
        Calculate Tree 2: Session Features score with Negative Scoring
        
        Args:
            record: Record to score
            
        Returns:
            Session features score [-1, 1] with penalty system
        """
        session_depth = record.get('session_depth', 1)
        duration = record.get('session_duration_minutes', 0)

        penalty = 0.0
        if session_depth <= 2:
            penalty -= self.penalty_low_depth
        if duration < 1.0:
            penalty -= self.penalty_short_duration

        bonus = (record.get('category_view_count', 0) / 5.0) * self.bonus_scale

        return bonus + penalty
    
    def predict_single(self, record: Dict[str, Any]) -> Tuple[int, float]:
        """
        Predict for a single record
        
        Args:
            record: Record to predict
            
        Returns:
            (prediction, probability)
        """
        f1 = self.calculate_rule_matching_score(record)
        f2 = self.calculate_session_features_score(record)

        weight_sum = self.weights['rule_matching'] + self.weights['session_features']
        combined_score = (
            (self.weights['rule_matching'] * f1) +
            (self.weights['session_features'] * f2)
        ) / max(weight_sum, 1e-6)

        prob = 1 / (1 + np.exp(-combined_score * self.sigmoid_scale))
        prediction = 1 if prob >= self.threshold else 0

        return prediction, prob
    
    def predict_batch(self, records: List[Dict[str, Any]]) -> Tuple[List[int], List[float]]:
        """
        Predict for batch of records
        
        Args:
            records: List of records
            
        Returns:
            (predictions, probabilities)
        """
        predictions = []
        probabilities = []
        
        for record in records:
            pred, prob = self.predict_single(record)
            predictions.append(pred)
            probabilities.append(prob)
        
        return predictions, probabilities
    
    def evaluate(self, records: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Evaluate model on records
        
        Args:
            records: Records with ground truth 'interest' labels
            
        Returns:
            Metrics dictionary
        """
        y_true = [r.get('interest', 0) for r in records]
        y_pred, y_prob = self.predict_batch(records)
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1_score': f1_score(y_true, y_pred, zero_division=0)
        }
        
        # ROC-AUC if we have both classes
        if len(set(y_true)) > 1:
            metrics['roc_auc'] = roc_auc_score(y_true, y_prob)
        else:
            metrics['roc_auc'] = 0.0
        
        return metrics

    def tune_hyperparameters(
        self,
        records: List[Dict[str, Any]],
        thresholds: Optional[List[float]] = None,
        weight_grid: Optional[List[Tuple[float, float]]] = None,
        penalty_grid: Optional[List[Tuple[float, float]]] = None
    ) -> Dict[str, Any]:
        """
        Grid search for threshold, weights, and session penalties.

        Returns best configuration and metrics.
        """
        if not records:
            return {'best_metrics': {}, 'best_params': {}}

        thresholds = thresholds or [0.45, 0.50, 0.55, 0.60]
        weight_grid = weight_grid or [(0.6, 0.4), (0.7, 0.3), (0.8, 0.2)]
        penalty_grid = penalty_grid or [(0.1, 0.1), (0.2, 0.2), (0.3, 0.2)]

        y_true = [r.get('interest', 0) for r in records]

        best = {
            'accuracy': -1.0,
            'f1_score': -1.0,
            'recall': -1.0
        }
        best_params = {}

        # Cache base scores to reduce repeated rule lookups
        base_scores = []
        for record in records:
            base_scores.append(self.calculate_rule_matching_score(record))

        for threshold in thresholds:
            for rule_w, session_w in weight_grid:
                weight_sum = rule_w + session_w
                for penalty_low_depth, penalty_short_duration in penalty_grid:
                    y_pred = []
                    y_prob = []

                    # Temporary set penalties for scoring
                    self.penalty_low_depth = penalty_low_depth
                    self.penalty_short_duration = penalty_short_duration

                    for i, record in enumerate(records):
                        f1 = base_scores[i]
                        f2 = self.calculate_session_features_score(record)
                        combined_score = (
                            (rule_w * f1) + (session_w * f2)
                        ) / max(weight_sum, 1e-6)
                        prob = 1 / (1 + np.exp(-combined_score * self.sigmoid_scale))
                        pred = 1 if prob >= threshold else 0
                        y_pred.append(pred)
                        y_prob.append(prob)

                    metrics = {
                        'accuracy': accuracy_score(y_true, y_pred),
                        'precision': precision_score(y_true, y_pred, zero_division=0),
                        'recall': recall_score(y_true, y_pred, zero_division=0),
                        'f1_score': f1_score(y_true, y_pred, zero_division=0)
                    }

                    is_better = (
                        metrics['accuracy'] > best['accuracy'] or
                        (metrics['accuracy'] == best['accuracy'] and metrics['f1_score'] > best['f1_score']) or
                        (metrics['accuracy'] == best['accuracy'] and metrics['f1_score'] == best['f1_score'] and metrics['recall'] > best['recall'])
                    )
                    if is_better:
                        best = metrics
                        best_params = {
                            'threshold': threshold,
                            'weights': {
                                'rule_matching': rule_w,
                                'session_features': session_w
                            },
                            'penalty_low_depth': penalty_low_depth,
                            'penalty_short_duration': penalty_short_duration
                        }

        # Apply best params to model
        if best_params:
            self.threshold = best_params['threshold']
            self.weights = best_params['weights']
            self.penalty_low_depth = best_params['penalty_low_depth']
            self.penalty_short_duration = best_params['penalty_short_duration']

        return {
            'best_metrics': best,
            'best_params': best_params
        }


class ModelTrainer:
    """
    Train and evaluate custom predictor
    """
    
    def __init__(self, rules: List[Dict[str, Any]],
                 graph_structure: Dict[str, Any],
                 train_records: List[Dict[str, Any]]):
        """
        Initialize trainer
        
        Args:
            rules: Association rules
            graph_structure: Placeholder structure
            train_records: Training records
        """
        self.rules = rules
        self.graph = graph_structure
        self.train_records = train_records
        
        # Calculate statistics
        self.statistics = self._calculate_statistics()
        
        # Initialize predictor
        self.predictor = CustomPredictor(rules, graph_structure, self.statistics)
    
    def _calculate_statistics(self) -> Dict[str, Any]:
        """Calculate normalization statistics"""
        from phase2_apriori_training import StatisticsCalculator
        
        stats = {
            'session_stats': StatisticsCalculator.calculate_session_stats(self.train_records),
            'category_stats': StatisticsCalculator.calculate_category_stats(self.train_records),
            'global_baseline': StatisticsCalculator.calculate_global_baseline(self.train_records)
        }
        
        return stats
    
    def train_on_train_set(self) -> Dict[str, float]:
        """
        Evaluate on training set
        
        Returns:
            Training metrics
        """
        print("\nEvaluating on training set...")
        metrics = self.predictor.evaluate(self.train_records)
        
        print("Training Metrics:")
        print(f"  - Accuracy:  {metrics['accuracy']:.4f}")
        print(f"  - Precision: {metrics['precision']:.4f}")
        print(f"  - Recall:    {metrics['recall']:.4f}")
        print(f"  - F1-Score:  {metrics['f1_score']:.4f}")
        print(f"  - ROC-AUC:   {metrics['roc_auc']:.4f}")
        
        return metrics

    def tune_on_train_set(self) -> Dict[str, Any]:
        """
        Grid search tuning on training set.

        Returns tuning summary.
        """
        print("\nTuning hyperparameters on training set...")
        result = self.predictor.tune_hyperparameters(self.train_records)

        best_metrics = result.get('best_metrics', {})
        best_params = result.get('best_params', {})

        if best_metrics:
            print("Tuning Results:")
            print(f"  - Best Accuracy:  {best_metrics.get('accuracy', 0):.4f}")
            print(f"  - Best Precision: {best_metrics.get('precision', 0):.4f}")
            print(f"  - Best Recall:    {best_metrics.get('recall', 0):.4f}")
            print(f"  - Best F1-Score:  {best_metrics.get('f1_score', 0):.4f}")

        if best_params:
            print("Best Params:")
            print(f"  - Threshold: {best_params.get('threshold')}")
            weights = best_params.get('weights', {})
            print(f"  - Weights: rule={weights.get('rule_matching')} session={weights.get('session_features')}")
            print(f"  - Penalty low depth: {best_params.get('penalty_low_depth')}")
            print(f"  - Penalty short duration: {best_params.get('penalty_short_duration')}")

        return result
    
    def get_model_artifacts(self) -> Dict[str, Any]:
        """
        Get model artifacts for export
        
        Returns:
            Model artifacts dictionary
        """
        return {
            'predictor': self.predictor,
            'statistics': self.statistics
        }
