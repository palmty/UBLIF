# QUICK START GUIDE (Phase 1)

## 🚀 Quick Start (5 minutes)

### Windows (PowerShell)

```powershell
cd "C:\path\to\ACGI"

# Create venv
py -3.12 -m venv .venv-win

# Activate venv
.\.venv-win\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# Run Phase 1
python main.py
```

---

### macOS / Linux

```bash
cd /path/to/ACGI

# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Phase 1
python main.py
```

---

## 📊 Expected Output

After successful execution, you should see:

```
✓ Phase 1 completed successfully!
  - Valid records: ~8,000
  - UBLDF output records: ~8,000
```

Output files are written to `outputs/`:

- `UBLDF.json`
- `data_processing_stats.json`
- `ubif_validation_report.json`, `compliance_audit_log.json`

---

## 📈 Dashboards

```powershell
# Metrics + pattern analysis dashboard
.\run_metrics_dashboard.bat
# or
streamlit run metrics_dashboard.py

# Data processing dashboard
streamlit run dashboard.py
```

---

## 🐛 Common Issues

### Issue: "Module not found"

```bash
pip install --upgrade -r requirements.txt
```

### Issue: "File too large"

The system handles large files via streaming. Ensure >2GB free disk space.

---

## 📁 Check Your Setup

```
ACGI/
├── config.yaml
├── output_raw.ndjson
├── main.py
├── metrics_dashboard.py
├── dashboard.py
├── README.md
├── requirements.txt
├── src/
│   ├── phase1_data_processing.py
│   └── utils/
└── outputs/ (created after Phase 1)
```

---

## 🎯 Next Steps

1. **Review metrics**: Check `outputs/data_processing_stats.json`
2. **Inspect validation**: Review `outputs/ubif_validation_report.json`
3. **Launch dashboard**: `streamlit run metrics_dashboard.py`
4. **Adjust parameters**: Modify `config.yaml` if needed

---

**Ready to start! 🚀**
