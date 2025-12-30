# QUICK START GUIDE

## 🚀 Quick Start (5 minutes)

### 1. Setup Environment

```bash
cd /Users/lab1/Documents/ACGI

# Make setup script executable
chmod +x setup.sh

# Run setup
./setup.sh
```

### 2. Activate Virtual Environment

```bash
source venv/bin/activate
```

### 3. Run the Pipeline

```bash
# Run all phases (30-60 minutes for full dataset)
python3 main.py --phase all
```

### 4. View Results

```bash
# Open HTML report in browser
open outputs/evaluation_report.html

# Or check terminal output for metrics
```

---

## 📊 Expected Output

After successful execution, you should see:

```
✓ Phase 1 completed successfully!
  - Valid records: ~8,000
  - Train set: 80%
  - Test set: 20%

✓ Phase 2 completed successfully!
  - Association rules: ~1,200
  - Graph nodes: ~500
  - Training accuracy: ~87%

✓ Phase 3 completed successfully!
  - Test accuracy: ~85%
  - F1-Score: ~79%
  - Visualizations: 4 charts
```

---

## 🐛 Common Issues

### Issue: "Module not found"

```bash
# Solution: Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: "Permission denied"

```bash
# Solution: Make scripts executable
chmod +x setup.sh
chmod +x main.py
```

### Issue: "File too large"

```
# Solution: System handles large files automatically
# Ensure you have >2GB free disk space
```

---

## 📁 Check Your Setup

Verify directory structure:

```bash
tree -L 2
```

Should show:

```
ACGI/
├── config.yaml
├── output_raw.ndjson
├── main.py
├── README.md
├── setup.sh
├── requirements.txt
├── src/
│   ├── phase1_data_processing.py
│   ├── phase2_apriori_training.py
│   ├── phase3_evaluation.py
│   └── utils/
├── outputs/ (created after Phase 1)
└── visualizations/ (created after Phase 3)
```

---

## 🎯 Next Steps

1. **Review Results**: Check `outputs/evaluation_report.html`
2. **Analyze Predictions**: Review `outputs/test_predictions.json`
3. **View Visualizations**: Check `visualizations/` folder
4. **Adjust Parameters**: Modify `config.yaml` if needed
5. **Re-run**: Try different configurations

---

## 💡 Tips

- **First run**: Use a smaller dataset to test
- **Monitor progress**: Watch terminal for progress bars
- **Check logs**: Review output files for detailed info
- **Adjust thresholds**: Lower min_support if no rules found
- **Memory issues**: Process in smaller batches

---

## 📞 Need Help?

1. Check `README.md` for detailed documentation
2. Review troubleshooting section
3. Check output logs for error messages
4. Contact ACGI technical team

---

**Ready to start! 🚀**
