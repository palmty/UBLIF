#!/usr/bin/env python3
"""
Streamlit Dashboard สำหรับ Data Processing Metrics Evaluation
แสดงสมการชี้วัดการประมวลผลข้อมูล (Data Processing Metrics) พร้อมการคำนวณ
"""

import streamlit as st
import json
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# กำหนด page config
st.set_page_config(
    page_title="Data Processing Metrics Evaluation",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_data():
    """โหลดข้อมูลจากไฟล์ JSON ต่างๆ"""
    data = {}
    
    # โหลด data processing stats
    try:
        with open('outputs/data_processing_stats.json', 'r', encoding='utf-8') as f:
            data['processing_stats'] = json.load(f)
    except FileNotFoundError:
        st.error("❌ ไม่พบไฟล์ data_processing_stats.json")
        st.info("💡 กรุณารัน Phase 1 ก่อนเพื่อสร้างข้อมูล")
        return None
    
    # โหลด compliance audit log
    try:
        with open('outputs/compliance_audit_log.json', 'r', encoding='utf-8') as f:
            data['compliance_audit'] = json.load(f)
    except FileNotFoundError:
        st.warning("⚠️ ไม่พบไฟล์ compliance_audit_log.json")
        data['compliance_audit'] = {}
    
    # โหลด ubif validation report (ถ้ามี)
    try:
        with open('outputs/ubif_validation_report.json', 'r', encoding='utf-8') as f:
            data['ubif_validation'] = json.load(f)
    except FileNotFoundError:
        data['ubif_validation'] = {}
    
    # โหลดข้อมูลสำหรับ pattern recognition
    try:
        # โหลดข้อมูล UBLDF sample สำหรับการวิเคราะห์ pattern
        with open('outputs/UBLDF.json', 'r', encoding='utf-8') as f:
            # อ่านเฉพาะ 10,000 records แรกเพื่อประสิทธิภาพ
            ubldf_data = json.load(f)
            data['train_sample'] = ubldf_data[:10000] if len(ubldf_data) > 10000 else ubldf_data
    except FileNotFoundError:
        st.warning("⚠️ ไม่พบไฟล์ UBLDF.json สำหรับการวิเคราะห์ pattern")
        data['train_sample'] = []

    return data

def haversine_km(lat1, lon1, lat2, lon2):
    """คำนวณระยะทาง (กิโลเมตร) ระหว่างพิกัด 2 จุดแบบ vectorized"""
    R = 6371.0  # รัศมีโลก (กม.)
    lat1r = np.radians(lat1)
    lat2r = np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

def analyze_patterns(train_data):
    """วิเคราะห์ patterns จากข้อมูล training"""
    if not train_data:
        return {}
    
    df = pd.DataFrame(train_data)
    patterns = {}
    
    # 1. Temporal Patterns
    if 'hour_of_day' in df.columns:
        patterns['hourly_activity'] = df.groupby('hour_of_day')['interest'].agg(['count', 'mean']).reset_index()
    
    if 'day_of_week' in df.columns:
        patterns['daily_activity'] = df.groupby('day_of_week')['interest'].agg(['count', 'mean']).reset_index()
    
    if 'is_weekend' in df.columns:
        patterns['weekend_vs_weekday'] = df.groupby('is_weekend')['interest'].agg(['count', 'mean']).reset_index()
    
    # 2. User Behavior Patterns
    if 'event_type' in df.columns:
        patterns['event_type_distribution'] = df.groupby('event_type')['interest'].agg(['count', 'mean']).reset_index()
    
    if 'category' in df.columns:
        patterns['category_patterns'] = df.groupby('category')['interest'].agg(['count', 'mean']).reset_index()
    
    if 'service_type' in df.columns:
        patterns['service_type_patterns'] = df.groupby('service_type')['interest'].agg(['count', 'mean']).reset_index()
    
    # 3. Session Patterns
    if 'session_depth' in df.columns:
        patterns['session_depth_distribution'] = df.groupby('session_depth')['interest'].agg(['count', 'mean']).reset_index()
        patterns['session_depth_stats'] = {
            'mean': df['session_depth'].mean(),
            'median': df['session_depth'].median(),
            'std': df['session_depth'].std(),
            'min': df['session_depth'].min(),
            'max': df['session_depth'].max()
        }
    
    if 'click_position' in df.columns:
        patterns['click_position_patterns'] = df.groupby('click_position')['interest'].agg(['count', 'mean']).reset_index()
    
    # 4. Geographic Patterns (ถ้ามีข้อมูล location)
    if 'lat' in df.columns and 'lon' in df.columns:
        # คำนวณการกระจายทางภูมิศาสตร์
        patterns['geographic_spread'] = {
            'lat_range': df['lat'].max() - df['lat'].min(),
            'lon_range': df['lon'].max() - df['lon'].min(), 
            'center_lat': df['lat'].mean(),
            'center_lon': df['lon'].mean()
        }
    
    # 5. Interest Prediction Patterns
    if 'interest' in df.columns:
        patterns['overall_interest_rate'] = df['interest'].mean()
        patterns['interest_by_hour'] = df.groupby('hour_of_day')['interest'].mean().to_dict() if 'hour_of_day' in df.columns else {}
        patterns['interest_by_category'] = df.groupby('category')['interest'].mean().to_dict() if 'category' in df.columns else {}
    
    # 6. Anomaly Detection Patterns
    if 'session_duration_minutes' in df.columns:
        session_durations = df['session_duration_minutes']
        q75, q25 = np.percentile(session_durations, [75, 25])
        iqr = q75 - q25
        patterns['session_anomalies'] = {
            'outlier_threshold_lower': q25 - 1.5 * iqr,
            'outlier_threshold_upper': q75 + 1.5 * iqr,
            'outlier_count': len(session_durations[(session_durations < q25 - 1.5 * iqr) | (session_durations > q75 + 1.5 * iqr)]),
            'total_sessions': len(session_durations)
        }
        patterns['session_duration_series'] = session_durations.dropna()

    # 7. Returning vs New Behavior (พฤติกรรมการกลับมา / ความคุ้นเคย)
    if 'viewed_category_before' in df.columns and 'interest' in df.columns:
        patterns['returning_behavior'] = (
            df.groupby('viewed_category_before')['interest'].agg(['count', 'mean']).reset_index()
        )

    if 'category_view_count' in df.columns and 'interest' in df.columns:
        patterns['category_view_count_patterns'] = (
            df.groupby('category_view_count')['interest'].agg(['count', 'mean']).reset_index()
        )

    # 8. Session Journey (จังหวะภายในเซสชัน)
    if 'time_since_last_click' in df.columns:
        patterns['time_since_last_click'] = df['time_since_last_click'].dropna()

    if 'previous_products' in df.columns:
        patterns['previous_products_count'] = df['previous_products'].apply(
            lambda x: len(x) if isinstance(x, (list, tuple)) else 0
        )

    # 9. Hour x Day-of-week Heatmap (ความหนาแน่นกิจกรรม 2 มิติ)
    if 'hour_of_day' in df.columns and 'day_of_week' in df.columns:
        patterns['hour_day_heatmap'] = df.pivot_table(
            index='day_of_week', columns='hour_of_day', values='interest',
            aggfunc='count', fill_value=0
        )

    # 10. Category x Service Type Heatmap
    if 'category' in df.columns and 'service_type' in df.columns:
        svc = df['service_type'].replace('', 'unknown').fillna('unknown')
        patterns['category_service_heatmap'] = pd.crosstab(df['category'], svc)

    # 11. Geographic (แผนที่ผู้ใช้ + ระยะทางถึงบริการ)
    if 'user_lat' in df.columns and 'user_lon' in df.columns:
        geo = pd.DataFrame({
            'user_lat': pd.to_numeric(df['user_lat'], errors='coerce'),
            'user_lon': pd.to_numeric(df['user_lon'], errors='coerce'),
        })
        if 'interest' in df.columns:
            geo['interest'] = df['interest'].values
        geo = geo.dropna(subset=['user_lat', 'user_lon'])
        geo = geo[geo['user_lat'].between(-90, 90) & geo['user_lon'].between(-180, 180)]
        # ตัดพิกัด (0,0) ที่มักเป็นค่าว่าง
        geo = geo[~((geo['user_lat'] == 0) & (geo['user_lon'] == 0))]
        if len(geo) > 0:
            patterns['geo_points'] = geo.sample(min(3000, len(geo)), random_state=42)

        if 'location' in df.columns:
            svc_lat = pd.to_numeric(
                df['location'].apply(lambda x: x.get('lat') if isinstance(x, dict) else np.nan),
                errors='coerce'
            )
            svc_lon = pd.to_numeric(
                df['location'].apply(lambda x: x.get('lon') if isinstance(x, dict) else np.nan),
                errors='coerce'
            )
            u_lat = pd.to_numeric(df['user_lat'], errors='coerce')
            u_lon = pd.to_numeric(df['user_lon'], errors='coerce')
            dist = haversine_km(u_lat, u_lon, svc_lat, svc_lon)
            dist = dist.replace([np.inf, -np.inf], np.nan).dropna()
            dist = dist[dist >= 0]
            if len(dist) > 0:
                patterns['user_service_distance'] = dist

    # 12. Top Services (บริการยอดนิยม)
    if 'service_name' in df.columns:
        ts = df['service_name'].replace('', np.nan).dropna()
        if len(ts) > 0:
            patterns['top_services'] = ts.value_counts().head(15)

    return patterns
    
    return data

def calculate_metrics(data):
    """คำนวณเมตริกตามสมการที่กำหนด"""
    processing_stats = data['processing_stats']
    compliance_audit = data.get('compliance_audit', {})
    ubif_validation = data.get('ubif_validation', {})
    
    # ข้อมูลหลัก
    total_input_records = processing_stats.get('total_input_records', 0)
    valid_records = processing_stats.get('valid_records', 0)
    rejected_records = processing_stats.get('rejected_records', 0)

    # Cleaning breakdown (ใช้กู้ค่า raw input ที่แท้จริงเมื่อเปิด stream_clean_first)
    cleaning_stats = processing_stats.get('cleaning_statistics', {})
    duplicates_removed = int(cleaning_stats.get('duplicates_removed', 0) or 0)
    test_accounts_removed = int(cleaning_stats.get('test_accounts_removed', 0) or 0)
    bot_traffic_removed = int(cleaning_stats.get('bot_traffic_removed', 0) or 0)
    missing_service_id_removed = int(cleaning_stats.get('missing_service_id_removed', 0) or 0)
    stopword_removed = int(
        cleaning_stats.get('stopword_removed', cleaning_stats.get('irrelevant_keyword_removed', 0)) or 0
    )

    raw_input_records = int(
        processing_stats.get(
            'raw_input_records',
            total_input_records
            + duplicates_removed
            + test_accounts_removed
            + bot_traffic_removed
            + missing_service_id_removed
            + stopword_removed
        )
        or 0
    )
    
    # ข้อมูลจาก compliance audit
    compliance_stats = compliance_audit.get('statistics', {})
    total_processed = compliance_stats.get('total_processed', 0)
    flagged_records = compliance_stats.get('flagged_records', 0)
    pdpa_anonymized = compliance_stats.get('pdpa_anonymized', 0)
    threats_detected = compliance_stats.get('threats_detected', 0)
    
    # คำนวณตามสมการ
    
    # 1. Valid Processed Records = Records entering UBIF - Rejected by UBIF
    valid_processed_records = int(ubif_validation.get('valid_records', valid_records) or valid_records)
    
    # 2. Invalid Processed Records = Records Failing Validation + Records Failing Compliance  
    records_failing_validation = rejected_records
    records_failing_compliance = flagged_records
    invalid_processed_records = records_failing_validation + records_failing_compliance
    
    # 3. Rejection Rate = (Invalid Processed Records / Total Input Records) × 100%
    rejection_rate = (invalid_processed_records / raw_input_records * 100) if raw_input_records > 0 else 0
    
    # 4. Compliance Rate = (Valid Processed Records / Total Input Records) × 100%
    compliance_rate = (valid_processed_records / raw_input_records * 100) if raw_input_records > 0 else 0
    
    # สมการเสริม
    # Success Rate = 100% - Rejection Rate = Compliance Rate
    success_rate = 100 - rejection_rate
    
    # Validation Efficiency = (Records Passing UBIF Standards / Total Input Records) × 100%
    validation_efficiency = (valid_records / raw_input_records * 100) if raw_input_records > 0 else 0
    
    # Legal Compliance Rate = (Records Meeting Legal Requirements / Valid Processed Records) × 100%
    records_meeting_legal = pdpa_anonymized - threats_detected
    legal_compliance_rate = (records_meeting_legal / valid_processed_records * 100) if valid_processed_records > 0 else 0
    
    return {
        'total_input_records': total_input_records,
        'raw_input_records': raw_input_records,
        'valid_processed_records': valid_processed_records,
        'invalid_processed_records': invalid_processed_records,
        'records_failing_validation': records_failing_validation,
        'records_failing_compliance': records_failing_compliance,
        'rejection_rate': rejection_rate,
        'compliance_rate': compliance_rate,
        'success_rate': success_rate,
        'validation_efficiency': validation_efficiency,
        'legal_compliance_rate': legal_compliance_rate,
        'pdpa_anonymized': pdpa_anonymized,
        'threats_detected': threats_detected,
        'records_meeting_legal': records_meeting_legal,
        'removed_duplicate': duplicates_removed,
        'removed_test_admin': test_accounts_removed,
        'removed_bot_crawler': bot_traffic_removed,
        'removed_missing_service_id': missing_service_id_removed,
        'removed_stopword_irrelevant': stopword_removed
    }

def display_equations():
    """แสดงสมการทางคณิตศาสตร์"""
    st.markdown("## 📐 สมการชี้วัดการประมวลผลข้อมูล (Data Processing Metrics)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🟢 สมการหลัก (Primary Equations)")
        
        st.markdown("**1. รายการที่ประมวลผลสำเร็จ (Valid Processed Records)**")
        st.latex(r"\text{Valid Processed Records} = \text{Total Input Records} - \text{Invalid Records}")
        
        st.markdown("**2. รายการที่ไม่ผ่านเกณฑ์ (Invalid Processed Records)**")
        st.latex(r"\text{Invalid Processed Records} = \text{Records Failing Validation} + \text{Records Failing Compliance}")
        
        st.markdown("**3. อัตราการปฏิเสธข้อมูล (Rejection Rate)**")
        st.latex(r"\text{Rejection Rate} = \left( \frac{\text{Invalid Processed Records}}{\text{Total Input Records}} \right) \times 100\%")
        
        st.markdown("**4. อัตราการปฏิบัติตามข้อกำหนด (Compliance Rate)**")
        st.latex(r"\text{Compliance Rate} = \left( \frac{\text{Valid Processed Records}}{\text{Total Input Records}} \right) \times 100\%")
    
    with col2:
        st.markdown("### 🔗 สมการที่เกี่ยวข้อง (Related Equations)")
        
        st.markdown("**Overall Success Rate:**")
        st.latex(r"\text{Success Rate} = 100\% - \text{Rejection Rate} = \text{Compliance Rate}")
        
        st.markdown("**Validation Efficiency:**")
        st.latex(r"\text{Validation Efficiency} = \left( \frac{\text{Records Passing UBIF Standards}}{\text{Total Input Records}} \right) \times 100\%")
        
        st.markdown("**Legal Compliance Rate:**")
        st.latex(r"\text{Legal Compliance Rate} = \left( \frac{\text{Records Meeting Legal Requirements}}{\text{Valid Processed Records}} \right) \times 100\%")

def display_calculated_metrics(metrics):
    """แสดงค่าที่คำนวณได้"""
    st.markdown("## 🧮 ผลการคำนวณ (Calculated Results)")
    st.info(
        f"Raw input records (reconstructed) = {metrics['raw_input_records']:,} | "
        f"Records entering UBIF validation = {metrics['total_input_records']:,}"
    )
    
    # Primary Metrics
    st.markdown("### 📊 เมตริกหลัก")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📋 Valid Processed Records",
            value=f"{metrics['valid_processed_records']:,}",
            help="Records passing UBIF validation"
        )
    
    with col2:
        st.metric(
            label="❌ Invalid Processed Records", 
            value=f"{metrics['invalid_processed_records']:,}",
            help="Records Failing Validation + Records Failing Compliance"
        )
    
    with col3:
        st.metric(
            label="📉 Rejection Rate",
            value=f"{metrics['rejection_rate']:.2f}%",
            help="(Invalid Records / Total Records) × 100%"
        )
    
    with col4:
        st.metric(
            label="✅ Compliance Rate",
            value=f"{metrics['compliance_rate']:.2f}%", 
            help="(Valid Records / Total Records) × 100%"
        )
    
    # Secondary Metrics
    st.markdown("### 📈 เมตริกเสริม")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="🎯 Success Rate",
            value=f"{metrics['success_rate']:.2f}%",
            delta=f"= {metrics['compliance_rate']:.2f}%",
            help="100% - Rejection Rate"
        )
    
    with col2:
        st.metric(
            label="🔍 Validation Efficiency", 
            value=f"{metrics['validation_efficiency']:.2f}%",
            help="Records Passing UBIF Standards / Total Records"
        )
    
    with col3:
        st.metric(
            label="⚖️ Legal Compliance Rate",
            value=f"{metrics['legal_compliance_rate']:.2f}%",
            help="Records Meeting Legal Requirements / Valid Records"
        )

def create_breakdown_chart(metrics):
    """สร้างแผนภูมิแสดงการแยกประเภทข้อมูล"""
    st.markdown("### 📊 การแยกประเภทข้อมูล (Data Breakdown)")
    
    # Sankey diagram แสดงการไหลของข้อมูล
    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=["Total Input Records", "Valid Records", "Invalid Records", 
                   "Records Passing Validation", "Records Failing Validation", 
                   "Records Meeting Compliance", "Records Failing Compliance"],
            color=["blue", "green", "red", "lightgreen", "orange", "darkgreen", "darkred"]
        ),
        link=dict(
            source=[0, 0, 1, 1, 2], 
            target=[1, 2, 3, 5, 4],
            value=[
                metrics['valid_processed_records'],
                max(metrics['raw_input_records'] - metrics['valid_processed_records'], 0),
                metrics['valid_processed_records'] - metrics['records_failing_compliance'],
                metrics['records_meeting_legal'],
                metrics['records_failing_validation']
            ]
        ))])
    
    fig.update_layout(
        title_text="Data Processing Flow", 
        font_size=12,
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)

def create_metrics_comparison(metrics):
    """สร้างแผนภูมิเปรียบเทียบเมตริก"""
    st.markdown("### 📈 การเปรียบเทียบเมตริก (Metrics Comparison)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gauge chart สำหรับ rates
        fig_gauge = go.Figure()
        
        rates = [
            ("Compliance Rate", metrics['compliance_rate'], "green"),
            ("Success Rate", metrics['success_rate'], "blue"), 
            ("Validation Efficiency", metrics['validation_efficiency'], "orange"),
            ("Legal Compliance Rate", metrics['legal_compliance_rate'], "purple")
        ]
        
        for i, (name, value, color) in enumerate(rates):
            fig_gauge.add_trace(go.Indicator(
                mode="gauge+number+delta",
                value=value,
                domain={'x': [0, 1], 'y': [0.75-i*0.25, 1-i*0.25]},
                title={'text': name},
                delta={'reference': 90},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 50], 'color': "lightgray"},
                        {'range': [50, 80], 'color': "yellow"}, 
                        {'range': [80, 100], 'color': "lightgreen"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75, 
                        'value': 95
                    }
                }
            ))
        
        fig_gauge.update_layout(
            title="Performance Rates (%)",
            height=600,
            font_size=10
        )
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col2:
        # Bar chart แสดงจำนวน records
        categories = [
            'Total Input Records',
            'Valid Processed Records', 
            'Records Meeting Legal Req.',
            'Invalid Processed Records',
            'Records Failing Validation', 
            'Records Failing Compliance'
        ]
        
        values = [
            metrics['raw_input_records'],
            metrics['valid_processed_records'],
            metrics['records_meeting_legal'], 
            metrics['invalid_processed_records'],
            metrics['records_failing_validation'],
            metrics['records_failing_compliance']
        ]
        
        colors = ['blue', 'green', 'darkgreen', 'red', 'orange', 'darkred']
        
        fig_bar = go.Figure([go.Bar(
            x=categories,
            y=values,
            marker_color=colors,
            text=[f"{v:,}" for v in values],
            textposition='auto'
        )])
        
        fig_bar.update_layout(
            title="Record Counts",
            xaxis_title="Categories",
            yaxis_title="Number of Records",
            xaxis={'tickangle': -45},
            height=600,
            font_size=10
        )
        st.plotly_chart(fig_bar, use_container_width=True)

def create_calculation_steps(metrics):
    """แสดงขั้นตอนการคำนวณ"""
    st.markdown("## 🧮 ขั้นตอนการคำนวณ (Calculation Steps)")
    
    with st.expander("📋 ดูขั้นตอนการคำนวณทั้งหมด"):
        st.markdown("### 1. Valid Processed Records")
        st.code(f"""
Valid Processed Records = Total Input Records - Invalid Records
    Valid Processed Records = {metrics['raw_input_records']:,} - {metrics['invalid_processed_records']:,}
Valid Processed Records = {metrics['valid_processed_records']:,}
        """)
        
        st.markdown("### 2. Invalid Processed Records")
        st.code(f"""
Invalid Processed Records = Records Failing Validation + Records Failing Compliance
Invalid Processed Records = {metrics['records_failing_validation']:,} + {metrics['records_failing_compliance']:,}
Invalid Processed Records = {metrics['invalid_processed_records']:,}
        """)
        
        st.markdown("### 3. Rejection Rate")
        st.code(f"""
Rejection Rate = (Invalid Processed Records / Total Input Records) × 100%
    Rejection Rate = ({metrics['invalid_processed_records']:,} / {metrics['raw_input_records']:,}) × 100%
Rejection Rate = {metrics['rejection_rate']:.2f}%
        """)
        
        st.markdown("### 4. Compliance Rate")
        st.code(f"""
Compliance Rate = (Valid Processed Records / Total Input Records) × 100%
    Compliance Rate = ({metrics['valid_processed_records']:,} / {metrics['raw_input_records']:,}) × 100%
Compliance Rate = {metrics['compliance_rate']:.2f}%
        """)
        
        st.markdown("### 5. Success Rate")
        st.code(f"""
Success Rate = 100% - Rejection Rate
Success Rate = 100% - {metrics['rejection_rate']:.2f}%
Success Rate = {metrics['success_rate']:.2f}%
        """)

def create_pattern_analysis(patterns):
    """แสดงการวิเคราะห์ Pattern Recognition"""
    if not patterns:
        st.warning("⚠️ ไม่สามารถโหลดข้อมูลสำหรับการวิเคราะห์ pattern ได้")
        return
    
    st.markdown("## Pattern Analysis Dashboard")
    st.markdown("### Behavior pattern analysis from data processing")
    
    # 1. Temporal Patterns
    if 'hourly_activity' in patterns:
        st.markdown("####  Temporal Patterns ")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Hourly activity pattern
            hourly_data = patterns['hourly_activity']
            fig_hourly = go.Figure()
            
            fig_hourly.add_trace(go.Scatter(
                x=hourly_data['hour_of_day'],
                y=hourly_data['count'],
                mode='lines+markers',
                name='Activity Count',
                line=dict(color='blue', width=3),
                marker=dict(size=8)
            ))
            
            fig_hourly.add_trace(go.Scatter(
                x=hourly_data['hour_of_day'],
                y=hourly_data['mean'] * hourly_data['count'].max(),
                mode='lines+markers',
                name='Interest Rate (scaled)',
                line=dict(color='red', width=2, dash='dash'),
                yaxis='y2'
            ))
            
            fig_hourly.update_layout(
                title="Hourly Activity Pattern",
                xaxis_title="Hour of Day",
                yaxis_title="Activity Count",
                yaxis2=dict(
                    title="Interest Rate",
                    overlaying='y',
                    side='right'
                ),
                height=400
            )
            st.plotly_chart(fig_hourly, use_container_width=True)
        
        with col2:
            # Daily activity pattern
            if 'daily_activity' in patterns:
                daily_data = patterns['daily_activity']
                day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
                
                fig_daily = go.Figure([go.Bar(
                    x=[day_names[int(day)] if day < 7 else f'Day {int(day)}' for day in daily_data['day_of_week']],
                    y=daily_data['count'],
                    marker_color='lightblue',
                    text=[f"{count:,}<br>{rate:.1%}" for count, rate in zip(daily_data['count'], daily_data['mean'])],
                    textposition='auto'
                )])
                
                fig_daily.update_layout(
                    title="Daily Activity Pattern",
                    xaxis_title="Day of Week",
                    yaxis_title="Activity Count",
                    height=400
                )
                st.plotly_chart(fig_daily, use_container_width=True)
    
    # 2. User Behavior Patterns  
    st.markdown("#### 👥 User Behavior Patterns (รูปแบบพฤติกรรมผู้ใช้)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if 'event_type_distribution' in patterns:
            event_data = patterns['event_type_distribution'].head(10)  # Top 10 events
            fig_events = px.pie(
                values=event_data['count'],
                names=event_data['event_type'],
                title="Event Type Distribution"
            )
            fig_events.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_events, use_container_width=True)
    
    with col2:
        if 'category_patterns' in patterns:
            cat_data = patterns['category_patterns']
            fig_category = go.Figure([go.Bar(
                x=cat_data['category'],
                y=cat_data['count'],
                marker_color='lightgreen',
                text=[f"{rate:.1%}" for rate in cat_data['mean']],
                textposition='auto'
            )])
            fig_category.update_layout(
                title="Category Interest Patterns",
                xaxis_title="Category",
                yaxis_title="Count",
                xaxis={'tickangle': -45}
            )
            st.plotly_chart(fig_category, use_container_width=True)
    
    with col3:
        if 'service_type_patterns' in patterns:
            service_data = patterns['service_type_patterns']
            fig_service = px.treemap(
                service_data,
                values='count',
                names='service_type',
                title="Service Type Hierarchy",
                color='mean',
                color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig_service, use_container_width=True)
    
    # 3. Session Patterns
    if 'session_depth_distribution' in patterns:
        st.markdown("#### 🔄 Session Patterns (รูปแบบเซสชัน)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            session_data = patterns['session_depth_distribution']
            
            fig_session = go.Figure()
            fig_session.add_trace(go.Histogram(
                x=session_data['session_depth'],
                y=session_data['count'],
                histfunc='sum',
                name='Session Depth Distribution',
                marker_color='orange'
            ))
            
            fig_session.update_layout(
                title="Session Depth Distribution",
                xaxis_title="Session Depth",
                yaxis_title="Frequency",
                height=400
            )
            st.plotly_chart(fig_session, use_container_width=True)
        
        with col2:
            # Session statistics
            if 'session_depth_stats' in patterns:
                stats = patterns['session_depth_stats']
                
                st.markdown("**Session Depth Statistics:**")
                col2a, col2b = st.columns(2)
                with col2a:
                    st.metric("Mean Depth", f"{stats['mean']:.2f}")
                    st.metric("Median Depth", f"{stats['median']:.2f}")
                with col2b:
                    st.metric("Min Depth", f"{stats['min']}")
                    st.metric("Max Depth", f"{stats['max']}")
                
                st.metric("Standard Deviation", f"{stats['std']:.2f}")
    
    # 4. Click Position Patterns
    if 'click_position_patterns' in patterns:
        st.markdown("#### 🖱️ Click Position Patterns (รูปแบบตำแหน่งคลิก)")
        
        click_data = patterns['click_position_patterns']
        
        fig_click = go.Figure()
        fig_click.add_trace(go.Bar(
            x=click_data['click_position'],
            y=click_data['count'],
            name='Click Count',
            marker_color='lightcoral'
        ))
        
        fig_click.add_trace(go.Scatter(
            x=click_data['click_position'],
            y=click_data['mean'] * click_data['count'].max(),
            mode='lines+markers',
            name='Interest Rate (scaled)',
            line=dict(color='green', width=3),
            yaxis='y2'
        ))
        
        fig_click.update_layout(
            title="Click Position vs Interest Rate",
            xaxis_title="Click Position",
            yaxis_title="Click Count", 
            yaxis2=dict(title="Interest Rate", overlaying='y', side='right'),
            height=400
        )
        st.plotly_chart(fig_click, use_container_width=True)
    
    # 5. Anomaly Detection
    if 'session_anomalies' in patterns:
        st.markdown("#### 🚨 Anomaly Detection (การตรวจจับความผิดปกติ)")
        
        anomalies = patterns['session_anomalies']
        outlier_rate = (anomalies['outlier_count'] / anomalies['total_sessions']) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Sessions", f"{anomalies['total_sessions']:,}")
        with col2:
            st.metric("Anomalous Sessions", f"{anomalies['outlier_count']:,}")  
        with col3:
            st.metric("Anomaly Rate", f"{outlier_rate:.2f}%")
        with col4:
            st.metric("Threshold Range", 
                     f"{anomalies['outlier_threshold_lower']:.1f} - {anomalies['outlier_threshold_upper']:.1f}")
    
    # 6. Interest Prediction Insights
    if 'overall_interest_rate' in patterns:
        st.markdown("#### 🎯 Interest Prediction Insights (ความเข้าใจเชิงลึกการทำนายความสนใช้)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            overall_rate = patterns['overall_interest_rate']
            st.metric("Overall Interest Rate", f"{overall_rate:.2%}")
            
            # Interest by hour heatmap
            if 'interest_by_hour' in patterns and patterns['interest_by_hour']:
                hours = list(range(24))
                interest_rates = [patterns['interest_by_hour'].get(hour, 0) for hour in hours]
                
                fig_heatmap = go.Figure(data=go.Heatmap(
                    z=[interest_rates],
                    x=hours,
                    y=['Interest Rate'],
                    colorscale='RdYlGn',
                    showscale=True
                ))
                
                fig_heatmap.update_layout(
                    title="Interest Rate by Hour (Heatmap)",
                    xaxis_title="Hour of Day",
                    height=200
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)
        
        with col2:
            # Interest by category
            if 'interest_by_category' in patterns and patterns['interest_by_category']:
                categories = list(patterns['interest_by_category'].keys())
                rates = list(patterns['interest_by_category'].values())
                
                fig_cat_interest = go.Figure([go.Bar(
                    x=categories,
                    y=rates,
                    marker_color='skyblue',
                    text=[f"{rate:.1%}" for rate in rates],
                    textposition='auto'
                )])
                
                fig_cat_interest.update_layout(
                    title="Interest Rate by Category",
                    xaxis_title="Category",
                    yaxis_title="Interest Rate",
                    xaxis={'tickangle': -45},
                    height=400
                )
                st.plotly_chart(fig_cat_interest, use_container_width=True)

    # 7. Returning vs New Behavior (พฤติกรรมการกลับมา / ความคุ้นเคย)
    if 'returning_behavior' in patterns or 'category_view_count_patterns' in patterns:
        st.markdown("#### 🔁 Returning vs New Behavior (ความคุ้นเคยกับหมวด)")

        col1, col2 = st.columns(2)

        with col1:
            if 'returning_behavior' in patterns:
                rb = patterns['returning_behavior']
                labels = {0: 'New (ไม่เคยดู)', 1: 'Returning (เคยดูแล้ว)'}
                fig_rb = go.Figure()
                fig_rb.add_trace(go.Bar(
                    x=[labels.get(int(v), str(v)) for v in rb['viewed_category_before']],
                    y=rb['count'],
                    name='Activity Count',
                    marker_color='lightsteelblue',
                    text=[f"interest {rate:.1%}" for rate in rb['mean']],
                    textposition='auto'
                ))
                fig_rb.update_layout(
                    title="New vs Returning: Count & Interest Rate",
                    xaxis_title="พฤติกรรม",
                    yaxis_title="Activity Count",
                    height=400
                )
                st.plotly_chart(fig_rb, use_container_width=True)

        with col2:
            if 'category_view_count_patterns' in patterns:
                cvc = patterns['category_view_count_patterns'].sort_values('category_view_count').head(20)
                fig_cvc = go.Figure()
                fig_cvc.add_trace(go.Bar(
                    x=cvc['category_view_count'],
                    y=cvc['count'],
                    name='Count',
                    marker_color='lightgray'
                ))
                fig_cvc.add_trace(go.Scatter(
                    x=cvc['category_view_count'],
                    y=cvc['mean'],
                    mode='lines+markers',
                    name='Interest Rate',
                    line=dict(color='crimson', width=3),
                    yaxis='y2'
                ))
                fig_cvc.update_layout(
                    title="Category View Count vs Interest Rate",
                    xaxis_title="จำนวนครั้งที่ดูหมวดนี้",
                    yaxis_title="Count",
                    yaxis2=dict(title="Interest Rate", overlaying='y', side='right'),
                    height=400
                )
                st.plotly_chart(fig_cvc, use_container_width=True)

    # 8. Weekend vs Weekday (วันหยุด vs วันทำงาน)
    if 'weekend_vs_weekday' in patterns:
        st.markdown("#### 📅 Weekend vs Weekday (วันหยุด vs วันทำงาน)")
        ww = patterns['weekend_vs_weekday']
        labels = {0: 'Weekday', 1: 'Weekend'}

        col1, col2 = st.columns(2)
        with col1:
            fig_ww = go.Figure([go.Bar(
                x=[labels.get(int(v), str(v)) for v in ww['is_weekend']],
                y=ww['count'],
                marker_color=['#4C78A8', '#F58518'],
                text=[f"{c:,}" for c in ww['count']],
                textposition='auto'
            )])
            fig_ww.update_layout(title="Activity Count", yaxis_title="Count", height=350)
            st.plotly_chart(fig_ww, use_container_width=True)
        with col2:
            fig_wwr = go.Figure([go.Bar(
                x=[labels.get(int(v), str(v)) for v in ww['is_weekend']],
                y=ww['mean'],
                marker_color=['#4C78A8', '#F58518'],
                text=[f"{r:.1%}" for r in ww['mean']],
                textposition='auto'
            )])
            fig_wwr.update_layout(title="Interest Rate", yaxis_title="Interest Rate", height=350)
            st.plotly_chart(fig_wwr, use_container_width=True)

    # 9. Session Journey (การเดินทางภายในเซสชัน)
    has_journey = any(k in patterns for k in [
        'session_depth_distribution', 'time_since_last_click',
        'session_duration_series', 'previous_products_count'
    ])
    if has_journey:
        st.markdown("#### 🛒 Session Journey (การเดินทางภายในเซสชัน)")

        col1, col2 = st.columns(2)

        with col1:
            # Funnel ตาม session depth
            if 'session_depth_distribution' in patterns:
                sd = patterns['session_depth_distribution'].sort_values('session_depth')
                sd = sd[sd['session_depth'] >= 0].head(12)
                fig_funnel = go.Figure(go.Funnel(
                    y=[f"Depth {int(d)}" for d in sd['session_depth']],
                    x=sd['count'],
                    textinfo="value+percent initial"
                ))
                fig_funnel.update_layout(title="Session Depth Funnel (จุด drop-off)", height=400)
                st.plotly_chart(fig_funnel, use_container_width=True)

        with col2:
            # Time since last click distribution
            if 'time_since_last_click' in patterns:
                tsc = patterns['time_since_last_click']
                upper = tsc.quantile(0.95) if len(tsc) > 0 else 0
                tsc_trim = tsc[tsc <= upper] if upper > 0 else tsc
                fig_tsc = go.Figure([go.Histogram(
                    x=tsc_trim, nbinsx=40, marker_color='mediumpurple'
                )])
                fig_tsc.update_layout(
                    title="Time Since Last Click (ตัด 5% บนสุด)",
                    xaxis_title="วินาที", yaxis_title="Frequency", height=400
                )
                st.plotly_chart(fig_tsc, use_container_width=True)

        col3, col4 = st.columns(2)

        with col3:
            # Session duration distribution
            if 'session_duration_series' in patterns:
                sds = patterns['session_duration_series']
                upper = sds.quantile(0.95) if len(sds) > 0 else 0
                sds_trim = sds[sds <= upper] if upper > 0 else sds
                fig_sds = go.Figure([go.Histogram(
                    x=sds_trim, nbinsx=40, marker_color='teal'
                )])
                fig_sds.update_layout(
                    title="Session Duration (นาที, ตัด 5% บนสุด)",
                    xaxis_title="นาที", yaxis_title="Frequency", height=400
                )
                st.plotly_chart(fig_sds, use_container_width=True)

        with col4:
            # Previous products count
            if 'previous_products_count' in patterns:
                ppc = patterns['previous_products_count'].value_counts().sort_index().head(15)
                fig_ppc = go.Figure([go.Bar(
                    x=ppc.index.astype(str), y=ppc.values, marker_color='goldenrod'
                )])
                fig_ppc.update_layout(
                    title="จำนวนสินค้าที่ดูก่อนหน้า (Previous Products)",
                    xaxis_title="จำนวนสินค้าก่อนหน้า", yaxis_title="Count", height=400
                )
                st.plotly_chart(fig_ppc, use_container_width=True)

    # 10. 2D Heatmaps
    if 'hour_day_heatmap' in patterns or 'category_service_heatmap' in patterns:
        st.markdown("#### 🔥 Activity Heatmaps (ความหนาแน่น 2 มิติ)")

        if 'hour_day_heatmap' in patterns:
            hm = patterns['hour_day_heatmap']
            day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            y_labels = [day_names[int(d)] if 0 <= int(d) < 7 else f'Day {int(d)}' for d in hm.index]
            fig_hd = go.Figure(data=go.Heatmap(
                z=hm.values,
                x=[f"{int(h):02d}" for h in hm.columns],
                y=y_labels,
                colorscale='YlOrRd',
                colorbar=dict(title="Count")
            ))
            fig_hd.update_layout(
                title="Activity Heatmap: Hour × Day of Week",
                xaxis_title="Hour of Day", yaxis_title="Day of Week", height=380
            )
            st.plotly_chart(fig_hd, use_container_width=True)

        if 'category_service_heatmap' in patterns:
            cs = patterns['category_service_heatmap']
            # จำกัด service type ที่พบบ่อยสุด 15 คอลัมน์ เพื่อให้อ่านง่าย
            top_cols = cs.sum(axis=0).sort_values(ascending=False).head(15).index
            cs = cs[top_cols]
            fig_cs = go.Figure(data=go.Heatmap(
                z=cs.values,
                x=list(cs.columns),
                y=list(cs.index),
                colorscale='Blues',
                colorbar=dict(title="Count")
            ))
            fig_cs.update_layout(
                title="Category × Service Type Heatmap",
                xaxis_title="Service Type", yaxis_title="Category",
                xaxis={'tickangle': -45}, height=420
            )
            st.plotly_chart(fig_cs, use_container_width=True)

    # 11. Geographic Patterns (ภูมิศาสตร์)
    if 'geo_points' in patterns or 'user_service_distance' in patterns:
        st.markdown("#### 🗺️ Geographic Patterns (การกระจายเชิงพื้นที่)")

        if 'geo_points' in patterns:
            geo = patterns['geo_points']
            color_arg = 'interest' if 'interest' in geo.columns else None
            fig_map = px.density_mapbox(
                geo, lat='user_lat', lon='user_lon', radius=8,
                center=dict(lat=geo['user_lat'].mean(), lon=geo['user_lon'].mean()),
                zoom=4, mapbox_style='open-street-map',
                title="User Location Density (ความหนาแน่นผู้ใช้)"
            )
            fig_map.update_layout(height=500, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_map, use_container_width=True)

            if color_arg:
                interested = geo[geo['interest'] == 1]
                if len(interested) > 0:
                    fig_scatter = px.scatter_mapbox(
                        interested, lat='user_lat', lon='user_lon',
                        center=dict(lat=interested['user_lat'].mean(), lon=interested['user_lon'].mean()),
                        zoom=4, mapbox_style='open-street-map',
                        title="ตำแหน่งผู้ใช้ที่สนใจ (interest = 1)",
                        opacity=0.5
                    )
                    fig_scatter.update_layout(height=500, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig_scatter, use_container_width=True)

        if 'user_service_distance' in patterns:
            dist = patterns['user_service_distance']
            upper = dist.quantile(0.95) if len(dist) > 0 else 0
            dist_trim = dist[dist <= upper] if upper > 0 else dist
            fig_dist = go.Figure([go.Histogram(
                x=dist_trim, nbinsx=40, marker_color='seagreen'
            )])
            fig_dist.update_layout(
                title="ระยะทางจากผู้ใช้ถึงบริการ (กม., ตัด 5% บนสุด)",
                xaxis_title="ระยะทาง (กม.)", yaxis_title="Frequency", height=400
            )
            st.plotly_chart(fig_dist, use_container_width=True)
            st.caption(
                f"ระยะทางเฉลี่ย {dist.mean():.1f} กม. | มัธยฐาน {dist.median():.1f} กม. | "
                f"สูงสุด {dist.max():.1f} กม."
            )

    # 12. Top Services (บริการยอดนิยม)
    if 'top_services' in patterns:
        st.markdown("#### 🏆 Top Services (บริการที่ถูกคลิกมากที่สุด)")
        ts = patterns['top_services'].sort_values(ascending=True)
        fig_ts = go.Figure([go.Bar(
            x=ts.values, y=ts.index, orientation='h', marker_color='indianred',
            text=[f"{v:,}" for v in ts.values], textposition='auto'
        )])
        fig_ts.update_layout(
            title="Top 15 Services by Activity",
            xaxis_title="Activity Count", yaxis_title="Service Name",
            height=500
        )
        st.plotly_chart(fig_ts, use_container_width=True)

def main():
    """ฟังก์ชันหลัก"""
    
    # Header
    st.title("📐 Data Processing Metrics Evaluation")
    st.markdown("### สมการชี้วัดการประมวลผลข้อมูล และการคำนวณ + Pattern Recognition")
    
    # โหลดข้อมูล
    with st.spinner("กำลังโหลดข้อมูล..."):
        data = load_data()
    
    if data is None:
        st.stop()
    
    # คำนวณเมตริก
    metrics = calculate_metrics(data)
    
    # วิเคราะห์ patterns
    with st.spinner("กำลังวิเคราะห์ patterns..."):
        patterns = analyze_patterns(data.get('train_sample', []))
    
    # แสดงข้อมูลเมื่อไหร่สร้าง
    generated_at = data['processing_stats'].get('generated_at', 'Unknown')
    if generated_at != 'Unknown':
        try:
            gen_time = datetime.fromisoformat(generated_at)
            st.info(f"📅 ข้อมูลสร้างเมื่อ: {gen_time.strftime('%d/%m/%Y %H:%M:%S')}")
        except:
            st.info(f"📅 ข้อมูลสร้างเมื่อ: {generated_at}")
    
    # Sidebar options
    st.sidebar.title("Dashboard Options")
    show_equations = st.sidebar.checkbox("แสดงสมการทางคณิตศาสตร์", True)
    show_metrics = st.sidebar.checkbox("แสดงผลการคำนวณ", True) 
    show_breakdown = st.sidebar.checkbox("แสดงการแยกประเภทข้อมูล", True)
    show_comparison = st.sidebar.checkbox("แสดงการเปรียบเทียบเมตริก", True)
    show_patterns = st.sidebar.checkbox("แสดงการวิเคราะห์ Pattern Recognition", True)
    show_steps = st.sidebar.checkbox("แสดงขั้นตอนการคำนวณ", False)
    
    # แสดงเนื้อหา
    if show_equations:
        display_equations()
        st.markdown("---")
    
    if show_metrics:
        display_calculated_metrics(metrics)
        st.markdown("---")
    
    if show_breakdown:
        create_breakdown_chart(metrics)
        st.markdown("---")
    
    if show_comparison:
        create_metrics_comparison(metrics)
        st.markdown("---")
    
    if show_patterns:
        create_pattern_analysis(patterns)
        st.markdown("---")
    
    if show_steps:
        create_calculation_steps(metrics)
    
    # Footer
    st.markdown("---")
    st.markdown("**📐 Data Processing Metrics Evaluation** | ACGI Project")

if __name__ == "__main__":
    main()