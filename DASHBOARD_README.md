# 📊 ACGI Data Processing Dashboard

Dashboard แสดงผลการประมวลผลข้อมูล PHASE 1: DATA PROCESSING PIPELINE และ EVALUATION ด้วย Streamlit

## 🎯 เมตริกที่แสดง

### เมตริกหลัก

- **Valid Processed Records**: จำนวน records ที่ผ่านการประมวลผลสำเร็จ
- **Invalid Processed Records**: จำนวน records ที่ไม่ผ่านการประมวลผล
- **Rejection Rate**: อัตราการปฏิเสธ records (%)
- **Compliance Rate**: อัตราการปฏิบัติตามข้อกำหนด (%)

### แผนภูมิและสถิติ

1. **Processing Overview**: ภาพรวมการประมวลผล (Valid vs Invalid, UBLDF output)
2. **Interest Distribution**: การแจกแจงของ interest labels ใน UBLDF
3. **Processing Timeline**: เวลาที่ใช้ในการประมวลผลแต่ละขั้นตอน
4. **Session Statistics**: สถิติเซสชันผู้ใช้
5. **Record Flow (Full Breakdown)**: Raw input, removed by duplicate/test-admin/bot/missing serviceId/stop-word, Passed Algorithm 1, Failed Algorithm 2 by rule, Entered/Flagged Algorithm 3 by law, Final output
6. **Runtime Pipeline + Definitions**: แสดงลำดับ pipeline ที่รันจริงตาม `stream_clean_first` และนิยาม `valid/rejected/removed/flagged/parsed`

## 🚀 วิธีการรัน Dashboard

### Windows

```bash
# รัน batch file
run_dashboard.bat

# หรือรันจาก command line
streamlit run dashboard.py
```

### Linux/Mac

```bash
# ทำให้ script รันได้
chmod +x run_dashboard.sh

# รัน shell script
./run_dashboard.sh

# หรือรันจาก command line
streamlit run dashboard.py
```

### รันด้วย Python โดยตรง

```bash
# ตรวจสอบ dependencies
pip install -r requirements.txt

# รัน dashboard
streamlit run dashboard.py --server.port 8501
```

## 🔧 การติดตั้ง Dependencies

```bash
pip install streamlit>=1.28.0 plotly>=5.17.0
```

หรือติดตั้งทั้งหมดจาก requirements.txt:

```bash
pip install -r requirements.txt
```

## 📁 ไฟล์ข้อมูลที่จำเป็น

Dashboard จะอ่านข้อมูลจากไฟล์ดังนี้:

### ไฟล์หลัก (จำเป็น)

- `outputs/data_processing_stats.json` - สถิติการประมวลผลข้อมูล

### ไฟล์เสริม (ไม่จำเป็น)

- `outputs/compliance_audit_log.json` - รายงานการตรวจสอบความปลอดภัย
- `outputs/ubif_validation_report.json` - รายงานการตรวจสอบมาตรฐาน UBIF

หากไม่พบไฟล์เสริม dashboard จะแสดงเฉพาะข้อมูลที่มี

## 🎛️ การใช้งาน Dashboard

### Sidebar Options

ใช้ checkbox ใน sidebar เพื่อเลือกส่วนที่ต้องการแสดง:

- ✅ แสดงเมตริกหลัก
- ✅ แสดงภาพรวมการประมวลผล
- ✅ แสดงการแจกแจง Interest
- ✅ แสดงเวลาการประมวลผล
- ✅ แสดงผลการประเมินโมเดล
- ✅ แสดงสถิติเซสชัน

### การเข้าถึง

- **URL**: http://localhost:8501
- **Port**: 8501 (default)

## 📊 รายละเอียดการคำนวณ

### Rejection Rate

```
Rejection Rate = (Invalid Records / Total Input Records) × 100%
```

### Compliance Rate

```
Compliance Rate = ((Total Processed - Flagged Records) / Total Processed) × 100%
```

### Interest Rate

```
Interest Rate = (Interest Records / Total Records) × 100%
```

## 🔄 การอัปเดตข้อมูล

เมื่อมีการรัน Phase 1 ใหม่:

1. Dashboard จะอ่านข้อมูลล่าสุดจากไฟล์ JSON
2. Refresh browser หรือรันคำสั่ง `streamlit run dashboard.py` ใหม่
3. ข้อมูลจะอัปเดตอัตโนมัติ

## 🎨 การปรับแต่ง

### เปลี่ยนหน้าต่าง Browser

แก้ไขใน `dashboard.py`:

```python
st.set_page_config(
    page_title="Your Custom Title",
    layout="wide"  # หรือ "centered"
)
```

### เปลี่ยน Port

```bash
streamlit run dashboard.py --server.port 8502
```

## 🐛 การแก้ไขปัญหา

### ปัญหาที่อาจเจอ

1. **ModuleNotFoundError**: ติดตั้ง dependencies ขาดหาย

   ```bash
   pip install -r requirements.txt
   ```

2. **FileNotFoundError**: รันไฟล์ `main.py --phase 1` ก่อนเปิด dashboard

3. **Port already in use**: เปลี่ยน port หรือปิดกระบวนการที่ใช้ port 8501

### การตรวจสอบสถานะ

```bash
# ตรวจสอบว่า Streamlit ทำงานอยู่
netstat -an | grep 8501

# ดูข้อมูลไฟล์
ls -la outputs/
```

## 📋 Changelog

- **v1.0**: Dashboard สำหรับ Phase 1 Data Processing
- เมตริกหลัก: Valid/Invalid Records, Rejection Rate, Compliance Rate
- แผนภูมิ: Processing Overview, Interest Distribution, Timeline
- รองรับ: Windows และ Linux/Mac

## 👥 ผู้พัฒนา

ACGI Project Team - 2026
