# 📐 Data Processing Metrics Evaluation Dashboard

Dashboard เฉพาะส่วน **Evaluation** ที่แสดงสมการชี้วัดการประมวลผลข้อมูล (Data Processing Metrics) พร้อมการคำนวณแบบละเอียด + **Pattern Recognition Analysis**

หมายเหตุเวอร์ชันล่าสุด: Dashboard จะคำนวณ `Raw input records` แบบ reconstructed อัตโนมัติจากสถิติ cleaning (duplicate/test-admin/bot/missing serviceId/stop-word) เพื่อให้ค่าตรงกับ flow จริงของ pipeline เมื่อเปิด `stream_clean_first`.

## 🎯 Features หลักใน Dashboard

### 📊 สมการชี้วัดการประมวลผลข้อมูล (Data Processing Metrics)

#### สมการหลัก (Primary Equations)

1. **รายการที่ประมวลผลสำเร็จ (Valid Processed Records)**

   ```
   Valid Processed Records = Total Input Records - Invalid Records
   ```

2. **รายการที่ไม่ผ่านเกณฑ์ (Invalid Processed Records)**

   ```
   Invalid Processed Records = Records Failing Validation + Records Failing Compliance
   ```

3. **อัตราการปฏิเสธข้อมูล (Rejection Rate)**

   ```
   Rejection Rate = (Invalid Processed Records / Total Input Records) × 100%
   ```

4. **อัตราการปฏิบัติตามข้อกำหนด (Compliance Rate)**
   ```
   Compliance Rate = (Valid Processed Records / Total Input Records) × 100%
   ```

#### สมการที่เกี่ยวข้อง (Related Equations)

- **Success Rate**: `100% - Rejection Rate = Compliance Rate`
- **Validation Efficiency**: `(Records Passing UBIF Standards / Total Input Records) × 100%`
- **Legal Compliance Rate**: `(Records Meeting Legal Requirements / Valid Processed Records) × 100%`

### 🔍 Pattern Recognition Analysis (ใหม่!)

#### 1. 🕐 Temporal Patterns (รูปแบบตามเวลา)

- **Hourly Activity Pattern**: กิจกรรมตามช่วงเวลาในวัน พร้อมกราฟ dual-axis
- **Daily Activity Pattern**: กิจกรรมตามวันในสัปดาห์
- **Weekend vs Weekday Analysis**: เปรียบเทียบรูปแบบวันธรรมดากับวันหยุด

#### 2. 👥 User Behavior Patterns (รูปแบบพฤติกรรมผู้ใช้)

- **Event Type Distribution**: Pie chart การกระจายตัวของประเภทกิจกรรม
- **Category Interest Patterns**: Bar chart รูปแบบความสนใจตามหมวดหมู่
- **Service Type Hierarchy**: Treemap ลำดับชั้นของประเภทบริการ

#### 3. 🔄 Session Patterns (รูปแบบเซสชัน)

- **Session Depth Distribution**: Histogram การกระจายของระดับความลึกเซสชัน
- **Session Statistics**: สถิติเซสชันแบบละเอียด (Mean, Median, Min, Max, Std)

#### 4. 🖱️ Click Position Patterns (รูปแบบตำแหน่งคลิก)

- **Click Position vs Interest Rate**: ความสัมพันธ์ตำแหน่งคลิกกับอัตราความสนใจ
- **Position Effectiveness Analysis**: วิเคราะห์ประสิทธิภาพของตำแหน่งการคลิก

#### 5. 🚨 Anomaly Detection (การตรวจจับความผิดปกติ)

- **Session Outlier Detection**: การตรวจจับเซสชันที่ผิดปกติ
- **Anomaly Rate Metrics**: เมตริกอัตราความผิดปกติ
- **Threshold Analysis**: การวิเคราะห์เกณฑ์ IQR

#### 6. 🎯 Interest Prediction Insights (ความเข้าใจเชิงลึก)

- **Overall Interest Rate**: อัตราความสนใจรวม
- **Interest by Hour Heatmap**: แผนที่ความร้อนความสนใจตามเวลา
- **Interest by Category Analysis**: ความสนใจตามหมวดหมู่

### 🔗 สมการที่เกี่ยวข้อง (Related Equations)

- **Success Rate**: `100% - Rejection Rate = Compliance Rate`
- **Validation Efficiency**: `(Records Passing UBIF Standards / Total Input Records) × 100%`
- **Legal Compliance Rate**: `(Records Meeting Legal Requirements / Valid Processed Records) × 100%`

## 🚀 วิธีรัน Dashboard

### Windows

```bash
# รัน batch file
run_metrics_dashboard.bat

# หรือรันด้วย command line
& ".venv-win\Scripts\python.exe" -m streamlit run metrics_dashboard.py --server.port 8502
```

### Linux/Mac

```bash
# ใช้ virtual environment
source .venv/bin/activate
streamlit run metrics_dashboard.py --server.port 8502
```

## 🌐 การเข้าถึง

- **URL**: http://localhost:8502
- **Port**: 8502 (ไม่ชน dashboard หลักที่ port 8501)

## 🎨 Features ใน Dashboard

### 1. 📐 แสดงสมการทางคณิตศาสตร์

- สมการหลักทั้ง 4 สมการ
- สมการเสริม 3 สมการ
- แสดงด้วย LaTeX/MathJax ที่สวยงาม

### 2. 🧮 ผลการคำนวณ (Calculated Results)

- **เมตริกหลัก**: Valid Records, Invalid Records, Rejection Rate, Compliance Rate
- **เมตริกเสริม**: Success Rate, Validation Efficiency, Legal Compliance Rate
- แสดงค่าพร้อม tooltip อธิบาย

### 3. 📊 การแยกประเภทข้อมูล (Data Breakdown)

- **Sankey Diagram**: แสดงการไหลของข้อมูลจาก Input ถึง Output
- แสดงเส้นทางการประมวลผลแบบภาพ

### 4. 📈 การเปรียบเทียบเมตริก (Metrics Comparison)

- **Gauge Charts**: แสดง percentage rates แบบ speedometer
- **Bar Charts**: แสดงจำนวน records แต่ละประเภท
- มีสีแยกประเภทชัดเจน

### 5. 🔍 Pattern Recognition Analysis (ใหม่!)

- **15+ Interactive Charts**: Line, Bar, Pie, Treemap, Heatmap, Histogram
- **6 หมวดการวิเคราะห์**: Temporal, Behavioral, Session, Click Position, Anomaly Detection, Interest Prediction
- **Real-time Analysis**: วิเคราะห์จากข้อมูลจริง 10,000 records จาก UBLDF.json
- **Advanced Visualizations**: Dual-axis charts, Color-coded patterns, Hover details
- **Anomaly Detection**: ตรวจจับค่าผิดปกติด้วยวิธี IQR
- **Behavioral Insights**: เข้าใจรูปแบบพฤติกรรมผู้ใช้เชิงลึก

### 6. 🧮 ขั้นตอนการคำนวณ (Calculation Steps)

- แสดงขั้นตอนการคำนวณทีละสมการ
- ใส่ตัวเลขจริงจากข้อมูล
- เข้าใจง่าย ตรวจสอบได้

## 📊 ข้อมูลจริงจากโปรเจกต์

ตัวอย่างผลลัพธ์จากข้อมูลปัจจุบัน:

```
📋 Total Input Records: 43,736
✅ Valid Processed Records: 43,736
❌ Invalid Processed Records: 0
📉 Rejection Rate: 0.00%
✅ Compliance Rate: 100.00%
🎯 Success Rate: 100.00%
🔍 Validation Efficiency: 100.00%
⚖️ Legal Compliance Rate: 100.00%
```

## 🎛️ Sidebar Options

- ✅ แสดงสมการทางคณิตศาสตร์
- ✅ แสดงผลการคำนวณ
- ✅ แสดงการแยกประเภทข้อมูล
- ✅ แสดงการเปรียบเทียบเมตริก
- ✅ **แสดงการวิเคราะห์ Pattern Recognition** (ใหม่!)
- ☐ แสดงขั้นตอนการคำนวณ (ปิดเป็นค่าเริ่มต้น)

## 📁 ไฟล์ข้อมูลที่ต้องการ

Dashboard จะอ่านข้อมูลจาก:

- **หลัก**: `outputs/data_processing_stats.json` (จำเป็น)
- **Pattern Analysis**: `outputs/UBLDF.json` (สำหรับการวิเคราะห์ pattern)
- **เสริม**: `outputs/compliance_audit_log.json` (ไม่จำเป็น)
- **เสริม**: `outputs/ubif_validation_report.json` (ไม่จำเป็น)

## 🔄 การอัปเดตข้อมูล

1. รัน Phase 1: `python main.py --phase 1`
2. Refresh dashboard หรือรันใหม่
3. ข้อมูลจะอัปเดตทันที

## 💡 Tips การใช้งาน

- **Math Equations**: ใช้ LaTeX rendering สวยงาม
- **Interactive Charts**: คลิกดูรายละเอียดได้
- **Responsive Design**: ใช้งานได้ทั้ง desktop/mobile
- **Calculation Verification**: ตรวจสอบการคำนวณได้ใน "ขั้นตอนการคำนวณ"

## 🆚 ความแตกต่างจาก Dashboard หลัก

| Feature           | Dashboard หลัก    | Metrics Dashboard |
| ----------------- | ----------------- | ----------------- |
| Focus             | Overview ทุกอย่าง | Evaluation เฉพาะ  |
| Math Equations    | ไม่มี             | มีครบทั้งหมด      |
| Calculation Steps | ไม่มี             | มีโดยละเอียด      |
| Port              | 8501              | 8502              |
| Sankey Diagram    | ไม่มี             | มี                |
| Gauge Charts      | ไม่มี             | มี                |

---

### 🎯 Specialized Dashboard for Data Processing Metrics Evaluation!

เฉพาะเจาะจงเรื่องสมการและการคำนวณเมตริก! 📐✨
