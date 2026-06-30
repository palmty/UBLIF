# Data Processing Pipeline (Phase 1)

A data processing pipeline for user behavior data, focused on UBIF standard validation, Thai legal compliance, data cleaning, interest labeling, sessionization, and producing a unified labeled dataset (UBLDF).

---

## 📋 Overview

This project implements **Phase 1: Data Processing**, which:

- **Validates** data according to UBIF standards (ISO 8601, W3C584, RFC 791/2460, IEEE 802.1AR, ISO/IEC 20324)
- **Complies** with Thai laws (PDPA 2562, Computer Crime Act 2550, Cybersecurity Act 2562, and others)
- **Cleans** data (duplicates, test accounts, bot traffic)
- **Labels** user interest (based on event types)
- **Sessionizes** events (30-minute window) and extracts features
- **Outputs** a single unified labeled dataset (`UBLDF.json`)

---

## 🎯 Key Features

### Data Processing (Phase 1)

- ✅ UBIF standard validation
- ✅ Legal compliance (PDPA anonymization, security checks)
- ✅ Data cleaning (duplicates, test accounts, bots)
- ✅ Interest labeling (event types)
- ✅ Session creation (30-minute window)
- ✅ Feature extraction (click position, session depth, etc.)
- ✅ Unified labeled dataset output (`UBLDF.json`)

---

## 📁 Project Structure

```
ACGI/
├── config.yaml                   # Configuration file
├── output_raw.ndjson            # Input data (NDJSON format)
├── main.py                      # Main execution script (Phase 1)
├── metrics_dashboard.py         # Streamlit metrics + pattern dashboard
├── dashboard.py                 # Streamlit data processing dashboard
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── src/                         # Source code
│   ├── __init__.py
│   ├── phase1_data_processing.py     # Phase 1 pipeline
│   │
│   └── utils/                        # Utility modules
│       ├── __init__.py
│       ├── ubif_validator.py         # UBIF validation
│       ├── legal_compliance.py       # PDPA/legal compliance
│       ├── data_cleaner.py           # Data cleaning + interest labeling
│       └── sessionizer.py            # Session creation
│
├── scripts/                     # Helper scripts
│   └── extract_standards_rejected_raw.py
│
└── outputs/                     # Output files
    ├── UBLDF.json                    # Unified labeled dataset (sessionized + features)
    ├── ubif_validation_report.json   # Validation report
    ├── compliance_audit_log.json     # Compliance audit log
    ├── rejected_records.json         # Rejected records (sample)
    ├── data_processing_stats.json    # Processing stats
    ├── standards_rejected_raw.json   # Raw records rejected by standards
    └── legal_flagged_samples.json    # Legal-flagged samples
```

---

## 🚀 Installation

### Prerequisites

- Python 3.9 or higher
- macOS / Linux / Windows (PowerShell)
- 8GB RAM minimum (16GB recommended for large datasets)

### Setup

1. **Navigate to the project directory.**

2. **Create and activate virtual environment:**

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
# py -3.12 -m venv .venv-win
# .\.venv-win\Scripts\Activate.ps1
```

3. **Install dependencies:**

```bash
pip install -r requirements.txt
```

---

## 📖 Usage

### Run Phase 1

```bash
python main.py
```

### Custom Paths

```bash
python main.py \
    --config /path/to/config.yaml \
    --input /path/to/output_raw.ndjson \
    --output /path/to/outputs
```

### Command Line Options

| Option     | Description               | Default             |
| ---------- | ------------------------- | ------------------- |
| `--config` | Path to config.yaml       | `config.yaml`       |
| `--input`  | Path to input NDJSON file | `output_raw.ndjson` |
| `--output` | Output directory          | `outputs/`          |

### Dashboards

```bash
# Metrics + pattern analysis dashboard
streamlit run metrics_dashboard.py

# Data processing dashboard
streamlit run dashboard.py
```

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

| Parameter        | Default | Description               |
| ---------------- | ------- | ------------------------- |
| `session_window` | 30      | Session timeout (minutes) |

---

## 📊 Output Files

**UBLDF.json** - Unified labeled dataset (sessionized records with features)

```json
[
  {
    "session_id": "abc123",
    "product_id": "18",
    "interest": 1,
    "timestamp": 1420114230,
    "click_position": 3,
    "session_depth": 8,
    "previous_products": ["12", "15"]
  }
]
```

**data_processing_stats.json** - Processing metrics (input/valid/rejected counts, output records, interest distribution, cleaning breakdown).

**ubif_validation_report.json** / **compliance_audit_log.json** - Validation and compliance audit details.

---

## ⚖️ Legal Compliance

### PDPA 2562 (Personal Data Protection Act)

- ✅ Account anonymization (SHA256)
- ✅ IP address masking
- ✅ Consent logging

### Computer Crime Act 2550

- ✅ SQL injection detection
- ✅ XSS attack detection
- ✅ Bot traffic removal
- ✅ Audit trail logging

---

## 🧪 Validate Output Files

```bash
# View first UBLDF record
python -c "import json; print(json.load(open('outputs/UBLDF.json'))[0])"

# Validate JSON
python -c "import json; json.load(open('outputs/data_processing_stats.json')); print('✓ Valid JSON')"
```

## .\run_metrics_dashboard.bat รัน dashbord

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

---

## 📝 License

Internal ACGI Project - Proprietary
© 2025 ACGI Team. All rights reserved.

---

Windows (PowerShell) note: prefer `python` (or `py -3.12`) instead of `python3`.
