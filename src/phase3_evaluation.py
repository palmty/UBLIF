"""
Phase 3: Evaluation and Visualization
Model evaluation, error analysis, and visualization generation
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
    confusion_matrix, roc_curve, classification_report
)
from tqdm import tqdm

from custom_predictor import CustomPredictor


class ModelEvaluator:
    """
    Evaluate model on test set
    """
    
    def __init__(self, test_path: str, rules_path: str, 
                 model_config_path: str, statistics_path: str):
        """
        Initialize evaluator
        
        Args:
            test_path: Path to test.json
            rules_path: Path to rules.json
            model_config_path: Path to model_config.json
            statistics_path: Path to train_statistics.json
        """
        self.test_path = test_path
        
        # Load test data
        print("Loading test data...")
        with open(test_path, 'r', encoding='utf-8') as f:
            self.test_records = json.load(f)
        print(f"✓ Loaded {len(self.test_records)} test records")
        
        # Load model artifacts
        print("Loading model artifacts...")
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules_data = json.load(f)
        
        with open(model_config_path, 'r', encoding='utf-8') as f:
            self.model_config = json.load(f)
        
        with open(statistics_path, 'r', encoding='utf-8') as f:
            self.statistics = json.load(f)
        
        # Initialize predictor
        self.predictor = CustomPredictor(
            rules=rules_data['rules'],
            graph_structure=rules_data['graph'],
            statistics=self.statistics
        )
        print("✓ Model loaded successfully")
        
        self.y_true = None
        self.y_pred = None
        self.y_prob = None
    
    def predict_test_set(self) -> Tuple[List[int], List[float]]:
        """
        Generate predictions for test set
        
        Returns:
            (predictions, probabilities)
        """
        print("\nGenerating predictions...")
        
        self.y_true = [r.get('interest', 0) for r in self.test_records]
        self.y_pred, self.y_prob = self.predictor.predict_batch(self.test_records)
        
        return self.y_pred, self.y_prob
    
    def calculate_metrics(self) -> Dict[str, float]:
        """
        Calculate evaluation metrics
        
        Returns:
            Metrics dictionary
        """
        print("\nCalculating metrics...")
        
        metrics = {
            'accuracy': accuracy_score(self.y_true, self.y_pred),
            'precision': precision_score(self.y_true, self.y_pred, zero_division=0),
            'recall': recall_score(self.y_true, self.y_pred, zero_division=0),
            'f1_score': f1_score(self.y_true, self.y_pred, zero_division=0)
        }
        
        # ROC-AUC
        if len(set(self.y_true)) > 1:
            metrics['roc_auc'] = roc_auc_score(self.y_true, self.y_prob)
        else:
            metrics['roc_auc'] = 0.0
        
        # Confusion matrix
        cm = confusion_matrix(self.y_true, self.y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        
        # True/False Positives/Negatives
        if cm.shape == (2, 2):
            tn, fp, fn, tp = cm.ravel()
            metrics['true_negatives'] = int(tn)
            metrics['false_positives'] = int(fp)
            metrics['false_negatives'] = int(fn)
            metrics['true_positives'] = int(tp)
        
        print("\nTest Set Metrics:")
        print(f"  - Accuracy:  {metrics['accuracy']:.4f}")
        print(f"  - Precision: {metrics['precision']:.4f}")
        print(f"  - Recall:    {metrics['recall']:.4f}")
        print(f"  - F1-Score:  {metrics['f1_score']:.4f}")
        print(f"  - ROC-AUC:   {metrics['roc_auc']:.4f}")
        
        return metrics
    
    def generate_classification_report(self) -> Dict[str, Any]:
        """
        Generate detailed classification report
        
        Returns:
            Classification report dictionary
        """
        report = classification_report(
            self.y_true, 
            self.y_pred,
            target_names=['No Interest', 'Interest'],
            output_dict=True,
            zero_division=0
        )
        
        return report


class ErrorAnalyzer:
    """
    Analyze prediction errors
    """
    
    def __init__(self, test_records: List[Dict[str, Any]], 
                 y_true: List[int], y_pred: List[int], y_prob: List[float]):
        """
        Initialize error analyzer
        
        Args:
            test_records: Test records
            y_true: Ground truth labels
            y_pred: Predictions
            y_prob: Prediction probabilities
        """
        self.test_records = test_records
        self.y_true = y_true
        self.y_pred = y_pred
        self.y_prob = y_prob
    
    def identify_false_positives(self) -> List[Dict[str, Any]]:
        """
        Identify false positive cases
        
        Returns:
            List of false positive records
        """
        false_positives = []
        
        for i, (true, pred) in enumerate(zip(self.y_true, self.y_pred)):
            if true == 0 and pred == 1:
                fp_case = {
                    'index': i,
                    'record': self.test_records[i],
                    'probability': self.y_prob[i]
                }
                false_positives.append(fp_case)
        
        return false_positives
    
    def identify_false_negatives(self) -> List[Dict[str, Any]]:
        """
        Identify false negative cases
        
        Returns:
            List of false negative records
        """
        false_negatives = []
        
        for i, (true, pred) in enumerate(zip(self.y_true, self.y_pred)):
            if true == 1 and pred == 0:
                fn_case = {
                    'index': i,
                    'record': self.test_records[i],
                    'probability': self.y_prob[i]
                }
                false_negatives.append(fn_case)
        
        return false_negatives
    
    def analyze_error_patterns(self) -> Dict[str, Any]:
        """
        Analyze patterns in errors
        
        Returns:
            Error analysis dictionary
        """
        false_positives = self.identify_false_positives()
        false_negatives = self.identify_false_negatives()
        
        # Analyze by category
        fp_categories = defaultdict(int)
        fn_categories = defaultdict(int)
        
        for fp in false_positives:
            category = fp['record'].get('category', 'unknown')
            fp_categories[category] += 1
        
        for fn in false_negatives:
            category = fn['record'].get('category', 'unknown')
            fn_categories[category] += 1
        
        analysis = {
            'total_false_positives': len(false_positives),
            'total_false_negatives': len(false_negatives),
            'fp_by_category': dict(fp_categories),
            'fn_by_category': dict(fn_categories),
            'sample_false_positives': false_positives[:10],
            'sample_false_negatives': false_negatives[:10]
        }
        
        print(f"\nError Analysis:")
        print(f"  - False Positives: {len(false_positives)}")
        print(f"  - False Negatives: {len(false_negatives)}")
        
        return analysis
    
    def identify_cold_start_issues(self) -> Dict[str, Any]:
        """
        Identify cold start problems (new products in test)
        
        Returns:
            Cold start analysis
        """
        # Products that appear in test but may have limited training data
        test_products = set(r.get('product_id') for r in self.test_records)
        
        # Products with errors
        error_products = set()
        for i, (true, pred) in enumerate(zip(self.y_true, self.y_pred)):
            if true != pred:
                error_products.add(self.test_records[i].get('product_id'))
        
        cold_start = {
            'total_test_products': len(test_products),
            'products_with_errors': len(error_products),
            'error_rate': len(error_products) / max(len(test_products), 1)
        }
        
        return cold_start


class VisualizationEngine:
    """
    Generate visualizations
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize visualization engine
        
        Args:
            output_dir: Directory to save visualizations
        """
        self.output_dir = output_dir
        
        # Set style
        sns.set_style('whitegrid')
        plt.rcParams['figure.figsize'] = (10, 8)
        plt.rcParams['font.size'] = 10
    
    def plot_confusion_matrix(self, cm: np.ndarray, save_name: str = 'confusion_matrix.png') -> None:
        """
        Plot confusion matrix
        
        Args:
            cm: Confusion matrix
            save_name: Filename to save
        """
        plt.figure(figsize=(8, 6))
        
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=['No Interest', 'Interest'],
                   yticklabels=['No Interest', 'Interest'])
        
        plt.title('Confusion Matrix', fontsize=14, fontweight='bold')
        plt.ylabel('True Label', fontsize=12)
        plt.xlabel('Predicted Label', fontsize=12)
        plt.tight_layout()
        
        save_path = os.path.join(self.output_dir, save_name)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved {save_path}")
    
    def plot_roc_curve(self, y_true: List[int], y_prob: List[float],
                      save_name: str = 'roc_curve.png') -> None:
        """
        Plot ROC curve
        
        Args:
            y_true: True labels
            y_prob: Prediction probabilities
            save_name: Filename to save
        """
        plt.figure(figsize=(8, 6))
        
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        auc = roc_auc_score(y_true, y_prob)
        
        plt.plot(fpr, tpr, linewidth=2, label=f'ROC Curve (AUC = {auc:.4f})')
        plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Random Classifier')
        
        plt.xlabel('False Positive Rate', fontsize=12)
        plt.ylabel('True Positive Rate', fontsize=12)
        plt.title('ROC Curve', fontsize=14, fontweight='bold')
        plt.legend(loc='lower right', fontsize=10)
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        save_path = os.path.join(self.output_dir, save_name)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved {save_path}")
    
    def plot_feature_importance(self, weights: Dict[str, float],
                               save_name: str = 'feature_importance.png') -> None:
        """
        Plot feature importance (tree weights)
        
        Args:
            weights: Weight dictionary
            save_name: Filename to save
        """
        plt.figure(figsize=(8, 6))
        
        features = list(weights.keys())
        values = list(weights.values())
        
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
        bars = plt.barh(features, values, color=colors)
        
        plt.xlabel('Weight', fontsize=12)
        plt.title('Feature Importance (Tree Weights)', fontsize=14, fontweight='bold')
        plt.xlim(0, max(values) * 1.2)
        
        # Add value labels
        for bar in bars:
            width = bar.get_width()
            plt.text(width + 0.01, bar.get_y() + bar.get_height()/2,
                    f'{width:.2f}', ha='left', va='center', fontsize=11)
        
        plt.tight_layout()
        
        save_path = os.path.join(self.output_dir, save_name)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved {save_path}")
    
    def plot_prediction_distribution(self, y_prob: List[float], y_true: List[int],
                                    save_name: str = 'prediction_distribution.png') -> None:
        """
        Plot prediction probability distribution
        
        Args:
            y_prob: Prediction probabilities
            y_true: True labels
            save_name: Filename to save
        """
        plt.figure(figsize=(10, 6))
        
        # Separate by true label
        prob_interest = [p for p, t in zip(y_prob, y_true) if t == 1]
        prob_no_interest = [p for p, t in zip(y_prob, y_true) if t == 0]
        
        plt.hist(prob_no_interest, bins=30, alpha=0.6, label='No Interest (True)', color='blue')
        plt.hist(prob_interest, bins=30, alpha=0.6, label='Interest (True)', color='orange')
        
        plt.xlabel('Prediction Probability', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title('Prediction Probability Distribution', fontsize=14, fontweight='bold')
        plt.legend(loc='upper right', fontsize=10)
        plt.axvline(x=0.5, color='red', linestyle='--', linewidth=1, label='Threshold')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        save_path = os.path.join(self.output_dir, save_name)
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"✓ Saved {save_path}")


class Phase3Pipeline:
    """
    Complete Phase 3 pipeline: Evaluation + Visualization
    """
    
    def __init__(self, test_path: str, output_dir: str, viz_dir: str):
        """
        Initialize Phase 3 pipeline
        
        Args:
            test_path: Path to test.json
            output_dir: Path to outputs directory
            viz_dir: Path to visualizations directory
        """
        self.test_path = test_path
        self.output_dir = output_dir
        self.viz_dir = viz_dir
        
        # Model artifact paths
        self.rules_path = os.path.join(output_dir, 'rules.json')
        self.model_config_path = os.path.join(output_dir, 'model_config.json')
        self.statistics_path = os.path.join(output_dir, 'train_statistics.json')
        
        print("Phase 3 Pipeline initialized!")
    
    def run_full_pipeline(self) -> None:
        """Run complete Phase 3 pipeline"""
        print("="*70)
        print("PHASE 3: EVALUATION + VISUALIZATION")
        print("="*70)
        
        start_time = datetime.now()
        
        # Step 3.1: Load and Evaluate
        print("\n=== STEP 3.1: MODEL EVALUATION ===")
        evaluator = ModelEvaluator(
            self.test_path,
            self.rules_path,
            self.model_config_path,
            self.statistics_path
        )
        
        y_pred, y_prob = evaluator.predict_test_set()
        metrics = evaluator.calculate_metrics()
        classification_rep = evaluator.generate_classification_report()
        
        # Step 3.2: Error Analysis
        print("\n=== STEP 3.2: ERROR ANALYSIS ===")
        analyzer = ErrorAnalyzer(
            evaluator.test_records,
            evaluator.y_true,
            evaluator.y_pred,
            evaluator.y_prob
        )
        
        error_analysis = analyzer.analyze_error_patterns()
        cold_start_analysis = analyzer.identify_cold_start_issues()
        
        # Step 3.3: Visualizations
        print("\n=== STEP 3.3: GENERATING VISUALIZATIONS ===")
        viz_engine = VisualizationEngine(self.viz_dir)
        
        # Confusion Matrix
        cm = np.array(metrics['confusion_matrix'])
        viz_engine.plot_confusion_matrix(cm)
        
        # ROC Curve
        if len(set(evaluator.y_true)) > 1:
            viz_engine.plot_roc_curve(evaluator.y_true, evaluator.y_prob)
        
        # Feature Importance
        with open(self.model_config_path, 'r') as f:
            model_config = json.load(f)
        weights = model_config['prediction']['weights']
        viz_engine.plot_feature_importance(weights)
        
        # Prediction Distribution
        viz_engine.plot_prediction_distribution(evaluator.y_prob, evaluator.y_true)
        
        # Step 3.4: Save Outputs
        print("\n=== STEP 3.4: SAVING OUTPUTS ===")
        self._save_outputs(
            evaluator.test_records,
            y_pred,
            y_prob,
            metrics,
            classification_rep,
            error_analysis,
            cold_start_analysis
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print("\n" + "="*70)
        print("PHASE 3 COMPLETED SUCCESSFULLY!")
        print("="*70)
        print(f"Total evaluation time: {duration:.2f} seconds")
        print(f"\nOutput files saved to: {self.output_dir}")
        print(f"Visualizations saved to: {self.viz_dir}")
    
    def _save_outputs(self, test_records: List[Dict[str, Any]],
                     y_pred: List[int], y_prob: List[float],
                     metrics: Dict[str, Any],
                     classification_report: Dict[str, Any],
                     error_analysis: Dict[str, Any],
                     cold_start_analysis: Dict[str, Any]) -> None:
        """Save all evaluation outputs"""
        
        # Save test_predictions.json
        predictions = []
        for i, record in enumerate(test_records):
            pred_record = {
                'product_id': record.get('product_id'),
                'true_label': record.get('interest'),
                'predicted_label': y_pred[i],
                'probability': y_prob[i],
                'session_id': record.get('session_id'),
                'category': record.get('category')
            }
            predictions.append(pred_record)
        
        pred_path = os.path.join(self.output_dir, 'test_predictions.json')
        with open(pred_path, 'w', encoding='utf-8') as f:
            json.dump(predictions, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {pred_path}")
        
        # Save evaluation_metrics.json
        eval_metrics = {
            'test_metrics': metrics,
            'classification_report': classification_report,
            'error_analysis': error_analysis,
            'cold_start_analysis': cold_start_analysis,
            'timestamp': datetime.now().isoformat()
        }
        
        metrics_path = os.path.join(self.output_dir, 'evaluation_metrics.json')
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump(eval_metrics, f, indent=2, ensure_ascii=False)
        print(f"✓ Saved {metrics_path}")
        
        # Generate simple HTML report
        self._generate_html_report(metrics, eval_metrics)
    
    def _generate_html_report(self, metrics: Dict[str, Any], 
                             full_metrics: Dict[str, Any]) -> None:
        """Generate HTML evaluation report"""
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Hybrid Recommendation System - Evaluation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin: 20px 0; }}
        .metric-card {{ background: #ecf0f1; padding: 20px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 36px; font-weight: bold; color: #2980b9; }}
        .metric-label {{ font-size: 14px; color: #7f8c8d; margin-top: 5px; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f5f5; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 Hybrid Recommendation System - Evaluation Report</h1>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>📊 Key Metrics</h2>
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value {'success' if metrics['accuracy'] >= 0.85 else 'warning'}">
                    {metrics['accuracy']:.2%}
                </div>
                <div class="metric-label">Accuracy</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {'success' if metrics['precision'] >= 0.80 else 'warning'}">
                    {metrics['precision']:.2%}
                </div>
                <div class="metric-label">Precision</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {'success' if metrics['recall'] >= 0.78 else 'warning'}">
                    {metrics['recall']:.2%}
                </div>
                <div class="metric-label">Recall</div>
            </div>
            <div class="metric-card">
                <div class="metric-value {'success' if metrics['f1_score'] >= 0.79 else 'warning'}">
                    {metrics['f1_score']:.2%}
                </div>
                <div class="metric-label">F1-Score</div>
            </div>
        </div>
        
        <h2>🔍 Confusion Matrix</h2>
        <table>
            <tr>
                <th></th>
                <th>Predicted: No Interest</th>
                <th>Predicted: Interest</th>
            </tr>
            <tr>
                <td><strong>True: No Interest</strong></td>
                <td>{metrics.get('true_negatives', 0)}</td>
                <td>{metrics.get('false_positives', 0)}</td>
            </tr>
            <tr>
                <td><strong>True: Interest</strong></td>
                <td>{metrics.get('false_negatives', 0)}</td>
                <td>{metrics.get('true_positives', 0)}</td>
            </tr>
        </table>
        
        <h2>⚠️ Error Analysis</h2>
        <p><strong>False Positives:</strong> {full_metrics['error_analysis']['total_false_positives']}</p>
        <p><strong>False Negatives:</strong> {full_metrics['error_analysis']['total_false_negatives']}</p>
        
        <h2>📈 Visualizations</h2>
        <ul>
            <li>Confusion Matrix: <code>visualizations/confusion_matrix.png</code></li>
            <li>ROC Curve: <code>visualizations/roc_curve.png</code></li>
            <li>Feature Importance: <code>visualizations/feature_importance.png</code></li>
            <li>Prediction Distribution: <code>visualizations/prediction_distribution.png</code></li>
        </ul>
        
        <div class="footer">
            <p>Hybrid Recommendation System (Apriori Graph + Custom XGBoost)</p>
            <p>ACGI Project - Version 1.0</p>
        </div>
    </div>
</body>
</html>
"""
        
        report_path = os.path.join(self.output_dir, 'evaluation_report.html')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"✓ Saved {report_path}")


def main():
    """Main entry point"""
    test_path = '/Users/lab1/Documents/ACGI/outputs/test.json'
    output_dir = '/Users/lab1/Documents/ACGI/outputs'
    viz_dir = '/Users/lab1/Documents/ACGI/visualizations'
    
    # Create viz directory if not exists
    os.makedirs(viz_dir, exist_ok=True)
    
    pipeline = Phase3Pipeline(test_path, output_dir, viz_dir)
    pipeline.run_full_pipeline()


if __name__ == '__main__':
    main()

