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
        
        # Weights for ensemble (re-balanced to reduce rule dominance)
        self.weights = {
            'rule_matching': 0.45,      # ลดลง (เพื่อให้ Rule ไม่ชี้นำทั้งหมด)
            'session_features': 0.55    # เพิ่มขึ้น (เพราะเราใส่ Logic ละเอียดแล้ว)
        }
        
        self.threshold = 0.40  # Decision threshold
    
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
            antecedents_set = set(rule['antecedents'])
            
            # Calculate overlap
            overlap = len(prev_set.intersection(antecedents_set))
            
            if overlap > 0:
                # Score based on overlap, confidence, and lift
                score = overlap * rule['confidence'] * rule['lift']
                
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
        
        if matched_rule:
            # Normalize confidence * lift
            score = matched_rule['confidence'] * min(matched_rule['lift'] / 100.0, 1.0)
            return min(score, 1.0)
        
        return 0.0
    
    def calculate_session_features_score(self, record: Dict[str, Any]) -> float:
        """
        Calculate Tree 2: Session Features score with Negative Scoring
        
        Args:
            record: Record to score
            
        Returns:
            Session features score [-1, 1] with penalty system
        """
        session_stats = self.stats.get('session_stats', {})
        
        # --- A. BOUNCE PENALTY (ลงโทษคนดูน้อย) ---
        # ถ้าดูน้อยกว่า 3 ชิ้น หรือ อยู่น้อยกว่า 1 นาที -> ให้ติดลบหนักๆ
        session_depth = record.get('session_depth', 1)
        duration = record.get('session_duration_minutes', 0)
        
        if session_depth <= 2 or duration < 1.0:
            return -0.8  # ตัดคะแนนทันที! (เกือบเต็ม -1)
        
        # 4. Session Duration & Depth: (0 ถึง 1)
        # Normalize session duration
        max_duration = max(session_stats.get('max_duration', 1), 1)
        duration = record.get('session_duration_minutes', 0)
        f_duration = min(duration / max_duration, 1.0)
        
        # Normalize click position (earlier is better)
        click_pos = record.get('click_position', 1)
        session_depth = max(record.get('session_depth', 1), 1)
        f_position = 1 - (click_pos / session_depth)
        
        # Previous products count (more context is better)
        prev_count = len(record.get('previous_products', []))
        f_prev = min(prev_count / 10.0, 1.0)
        
        # 1. Hour: ให้คะแนนเป็นช่วง (-0.5 ถึง 0.5)
        # เที่ยงวัน = +0.5, เที่ยงคืน = -0.5
        hour = record.get('hour_of_day', 12)
        dist_from_noon = abs(hour - 12)
        f_hour = (1 - (dist_from_noon / 12.0)) - 0.5 
        
        # 2. Location: ให้คะแนนเป็นช่วง (-0.5 ถึง 0.5)
        user_lat = record.get('user_lat', 13.0)
        # สมมติ Target Zone คือภาคกลาง/อีสาน (Lat 13-16)
        if 13.0 <= user_lat <= 16.0:
            f_lat = 0.5  # อยู่ในพื้นที่เป้าหมาย = บวก
        else:
            f_lat = -0.5 # อยู่นอกพื้นที่ = ลบ
        
        # --- B. SCALING (ปรับให้ค่าบวกยากขึ้น) ---
        # 3. Category Views: ต้องดูซ้ำ 3 ครั้งขึ้นไปถึงจะได้คะแนนเต็ม
        category_views = record.get('category_view_count', 0)
        f_category_views = min(max(0, category_views - 1) / 4.0, 1.0) 
        
        # --- รวมคะแนนแบบใหม่ ---
        score = (
            0.25 * f_duration +      # ถ้าดูนาน ช่วยดึงคะแนนขึ้น
            0.15 * f_position +
            0.10 * f_prev +
            0.20 * f_hour +          # มีสิทธิ์ติดลบ
            0.15 * f_lat +           # มีสิทธิ์ติดลบ
            0.15 * f_category_views
        )
        
        # Clip ผลลัพธ์ให้อยู่ในช่วง -1 ถึง 1
        return max(-1.0, min(1.0, score))
    
    def predict_single(self, record: Dict[str, Any]) -> Tuple[int, float]:
        """
        Predict for a single record
        
        Args:
            record: Record to predict
            
        Returns:
            (prediction, probability)
        """
        # Calculate scores for each tree
        f1 = self.calculate_rule_matching_score(record)
        f2 = self.calculate_session_features_score(record)
        
        # Weighted combination
        combined_score = (
            self.weights['rule_matching'] * f1 +
            self.weights['session_features'] * f2
        )
        
        # ลบ Bias ออก หรือลดลงเหลือแค่นิดเดียว
        # adjusted_score = combined_score - 0.3  <-- ลบบรรทัดนี้ทิ้ง หรือเปลี่ยนเป็น -0.1
        
        # Sigmoid
        prob = 1 / (1 + np.exp(-combined_score * 5)) # ใช้ combined_score เพียวๆ เลย
        
        # ปรับ Threshold ให้รับกับกราฟ
        # แนะนำให้ลองที่ 0.40 ดูครับ (จากเดิมที่กราฟกองอยู่แถวๆ นั้น)
        prediction = 1 if prob > 0.40 else 0 
        
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
