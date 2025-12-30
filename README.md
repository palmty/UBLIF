# Hybrid Recommendation System

## (Apriori Graph + Custom XGBoost)

A comprehensive recommendation system combining association rule mining (Apriori) with custom gradient boosting prediction for user interest prediction.

---

## 📋 Overview

This project implements a hybrid recommendation system that:

- **Validates** data according to UBIF standards (ISO 8601, W3C584, RFC 791/2460, IEEE 802.1AR, ISO/IEC 20324:2012)
- **Complies** with Thai laws (PDPA 2562, Computer Crime Act 2550)
- **Processes** user behavior data with sessionization and feature extraction
- **Trains** using Apriori algorithm to find association rules
- **Builds** a knowledge graph from product relationships
- **Predicts** user interest using custom gradient boosting formula
- **Evaluates** model performance with comprehensive metrics and visualizations

---

## 🎯 Key Features

### Data Processing (Phase 1)

- ✅ UBIF standard validation
- ✅ Legal compliance (PDPA anonymization, security checks)
- ✅ Data cleaning (duplicates, test accounts, bots)
- ✅ Interest labeling (31 event types)
- ✅ Session creation (30-minute window)
- ✅ Feature extraction (click position, session depth, etc.)
- ✅ Temporal train/test split (80:20)

### Model Training (Phase 2)

- ✅ Transaction matrix creation from sessions
- ✅ Apriori algorithm (min_support=0.015, min_confidence=0.60)
- ✅ Association rule generation
- ✅ Knowledge graph construction
- ✅ Graph features (PageRank, degrees, centrality)
- ✅ Custom prediction formula (3-tree ensemble)
- ✅ Model artifact export

### Evaluation (Phase 3)

- ✅ Test set evaluation
- ✅ Comprehensive metrics (Accuracy, Precision, Recall, F1, ROC-AUC)
- ✅ Error analysis
- ✅ Cold start detection
- ✅ Visualizations (confusion matrix, ROC curve, etc.)
- ✅ HTML report generation

---

## 📁 Project Structure

```
ACGI/
├── config.yaml                   # Configuration file
├── output_raw.ndjson            # Input data (NDJSON format)
├── main.py                      # Main execution script
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── src/                         # Source code
│   ├── __init__.py
│   ├── phase1_data_processing.py     # Phase 1 pipeline
│   ├── phase2_apriori_training.py    # Phase 2 pipeline
│   ├── phase3_evaluation.py          # Phase 3 pipeline
│   ├── custom_predictor.py           # Custom prediction model
│   │
│   └── utils/                        # Utility modules
│       ├── __init__.py
│       ├── ubif_validator.py         # UBIF validation
│       ├── legal_compliance.py       # PDPA/legal compliance
│       ├── data_cleaner.py           # Data cleaning
│       └── sessionizer.py            # Session creation
│
├── outputs/                     # Output files
│   ├── train.json                    # Training data (80%)
│   ├── test.json                     # Test data (20%)
│   ├── rules.json                    # Apriori rules + graph
│   ├── model_config.json             # Model configuration
│   ├── train_statistics.json         # Training statistics
│   ├── train_evaluation.json         # Training metrics
│   ├── test_predictions.json         # Test predictions
│   ├── evaluation_metrics.json       # Test metrics
│   ├── evaluation_report.html        # HTML report
│   ├── ubif_validation_report.json   # Validation report
│   └── data_processing_stats.json    # Processing stats
│
├── visualizations/              # Generated visualizations
│   ├── confusion_matrix.png
│   ├── roc_curve.png
│   ├── feature_importance.png
│   └── prediction_distribution.png
│
└── tests/                       # Test suite (optional)
    └── ...
```

---

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- macOS (as specified)
- 8GB RAM minimum (16GB recommended for large datasets)

### Setup

1. **Clone or navigate to the project directory:**

```bash
cd /Users/lab1/Documents/ACGI
```

2. **Create and activate virtual environment:**

```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

4. **Verify installation:**

```bash
python3 -c "import pandas, numpy, mlxtend, networkx, sklearn; print('✓ All dependencies installed')"
```

---

## 📖 Usage

### Quick Start - Run All Phases

Run the complete pipeline (all 3 phases):

```bash
python3 main.py --phase all
```

### Run Individual Phases

**Phase 1: Data Processing**

```bash
python3 main.py --phase 1
```

**Phase 2: Training**

```bash
python3 main.py --phase 2
```

**Phase 3: Evaluation**

```bash
python3 main.py --phase 3
```

### Custom Paths

```bash
python3 main.py \
    --phase all \
    --config /path/to/config.yaml \
    --input /path/to/output_raw.ndjson \
    --output /path/to/outputs \
    --viz /path/to/visualizations
```

### Command Line Options

| Option     | Description                       | Default             |
| ---------- | --------------------------------- | ------------------- |
| `--phase`  | Which phase to run (all, 1, 2, 3) | `all`               |
| `--config` | Path to config.yaml               | `config.yaml`       |
| `--input`  | Path to input NDJSON file         | `output_raw.ndjson` |
| `--output` | Output directory                  | `outputs/`          |
| `--viz`    | Visualizations directory          | `visualizations/`   |

---

## 🔧 Configuration

### config.yaml Structure

```yaml
ubif_filters:
  enabled: true
  strict_mode: true

  standards:
    - name: "ISO_8601"
      field: "customValue.datetime"
      pattern: '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'
      required: true

  legal_compliance:
    - name: "PDPA_2562"
      rules:
        - type: "anonymize_pii"
          method: "hash_sha256"

  data_quality:
    - name: "remove_duplicates"
      enabled: true
      window_seconds: 1
```

### Key Parameters

| Parameter          | Default | Description                        |
| ------------------ | ------- | ---------------------------------- |
| `min_support`      | 0.015   | Minimum support for Apriori (1.5%) |
| `min_confidence`   | 0.60    | Minimum confidence for rules (60%) |
| `min_lift`         | 1.5     | Minimum lift for rules             |
| `max_len`          | 5       | Maximum itemset length             |
| `session_window`   | 30      | Session timeout (minutes)          |
| `train_test_split` | 0.8     | Train/test split ratio             |

---

## 📊 Output Files

### Phase 1 Outputs

**train.json** - Training data (80%)

```json
[
  {
    "session_id": "abc123",
    "product_id": "18",
    "interest": 1,
    "timestamp": 1420114230,
    "click_position": 3,
    "session_depth": 8,
    "previous_products": ["12", "15"],
    ...
  }
]
```

**test.json** - Test data (20%)

- Same structure as train.json

### Phase 2 Outputs

**rules.json** - Association rules and graph

```json
{
  "metadata": {
    "algorithm": "apriori",
    "total_rules": 1200,
    "total_products": 500
  },
  "rules": [...],
  "graph": {
    "nodes": [...],
    "edges": [...]
  }
}
```

**model_config.json** - Model configuration

```json
{
  "version": "1.0",
  "prediction": {
    "method": "custom_gradient_boosting",
    "weights": {
      "rule_matching": 0.5,
      "graph_features": 0.3,
      "session_features": 0.2
    }
  }
}
```

### Phase 3 Outputs

**evaluation_metrics.json** - Test metrics

```json
{
  "test_metrics": {
    "accuracy": 0.85,
    "precision": 0.8,
    "recall": 0.78,
    "f1_score": 0.79,
    "roc_auc": 0.88
  }
}
```

**evaluation_report.html** - Interactive HTML report

- Open in browser for formatted results

---

## 📈 Performance Expectations

### Target Metrics

- ✅ **Accuracy**: ≥ 85%
- ✅ **Precision**: ≥ 80%
- ✅ **Recall**: ≥ 78%
- ✅ **F1-Score**: ≥ 79%
- ✅ **ROC-AUC**: ≥ 85%

### Processing Times (10K records)

- **Phase 1**: ~10 minutes
- **Phase 2**: ~15 minutes
- **Phase 3**: ~5 minutes
- **Total**: ~30 minutes

---

## 🔬 Model Architecture

### Custom Prediction Formula

The model combines three weighted trees:

**Tree 1: Rule Matching (50%)**

- Matches previous products to association rules
- Uses confidence × lift for scoring

**Tree 2: Graph Features (30%)**

- In-degree, out-degree, PageRank
- Captures product centrality in network

**Tree 3: Session Features (20%)**

- Session duration, click position
- Previous products count

**Final Prediction:**

```python
score = 0.5 * f1 + 0.3 * f2 + 0.2 * f3
probability = sigmoid(score)
prediction = 1 if probability > 0.5 else 0
```

---

## ⚖️ Legal Compliance

### PDPA 2562 (Personal Data Protection Act)

- ✅ Account anonymization (SHA256)
- ✅ IP address masking
- ✅ Consent logging
- ✅ Data retention policies

### Computer Crime Act 2550

- ✅ SQL injection detection
- ✅ XSS attack detection
- ✅ Bot traffic removal
- ✅ Audit trail logging

---

## 🐛 Troubleshooting

### Common Issues

**1. File size too large error**

```
Solution: The system handles large files via streaming.
Ensure sufficient disk space (>2GB free).
```

**2. Memory error during processing**

```
Solution: Process data in smaller batches by modifying
the batch size in phase1_data_processing.py
```

**3. No rules generated**

```
Solution: Lower min_support or min_confidence in config.yaml
min_support: 0.01 (1%)
min_confidence: 0.50 (50%)
```

**4. Module import errors**

```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

**5. Visualization errors**

```bash
# Check matplotlib backend
python3 -c "import matplotlib; print(matplotlib.get_backend())"
# If issues, set backend in code or install GUI backend
```

---

## 🧪 Testing

### Run Unit Tests

```bash
# Not yet implemented
pytest tests/
```

### Validate Output Files

```bash
python3 -c "import json; json.load(open('outputs/rules.json')); print('✓ Valid JSON')"
```

### Check Data Quality

```bash
# View first record
python3 -c "import json; print(json.load(open('outputs/train.json'))[0])"
```

---

## 📚 API Reference

### Phase 1: DataProcessingPipeline

```python
from src.phase1_data_processing import DataProcessingPipeline

pipeline = DataProcessingPipeline(
    config_path='config.yaml',
    input_file='output_raw.ndjson',
    output_dir='outputs/'
)
pipeline.run_full_pipeline()
```

### Phase 2: Phase2Pipeline

```python
from src.phase2_apriori_training import Phase2Pipeline

pipeline = Phase2Pipeline(
    config_path='config.yaml',
    train_path='outputs/train.json',
    output_dir='outputs/'
)
pipeline.run_full_pipeline()
```

### Phase 3: Phase3Pipeline

```python
from src.phase3_evaluation import Phase3Pipeline

pipeline = Phase3Pipeline(
    test_path='outputs/test.json',
    output_dir='outputs/',
    viz_dir='visualizations/'
)
pipeline.run_full_pipeline()
```

---

## 🤝 Contributing

This is an internal ACGI project. For modifications:

1. Create a new branch
2. Make changes
3. Test thoroughly
4. Submit for review

---

## 📝 License

Internal ACGI Project - Proprietary
© 2025 ACGI Team. All rights reserved.

---

## 👥 Team

**ACGI Project Team**

- Data Science Team
- Engineering Team
- Compliance Team

---

## 📞 Support

For issues or questions:

- Check the troubleshooting section
- Review output logs in terminal
- Contact the ACGI technical team

---

## 🔄 Version History

### Version 1.0 (2025-12-23)

- ✅ Initial release
- ✅ Complete 3-phase pipeline
- ✅ UBIF validation
- ✅ Legal compliance (PDPA, Computer Crime Act)
- ✅ Apriori + Graph + Custom XGBoost
- ✅ Comprehensive evaluation
- ✅ Visualization suite

---

## 🎯 Future Enhancements

- [ ] Real-time prediction API
- [ ] Database integration
- [ ] Model retraining pipeline
- [ ] A/B testing framework
- [ ] Dashboard for monitoring
- [ ] Mobile app integration

---

**Happy Recommending! 🚀**

ทดสอบ python3 src/compare_and_test.py
รันทั้งหมด python3 main.py --phase all
