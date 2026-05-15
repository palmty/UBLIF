#!/usr/bin/env python3
"""
Streamlit Dashboard for PHASE 1: DATA PROCESSING PIPELINE และ EVALUATION
แสดงเมตริก: Valid Processed Records, Invalid Processed Records, Rejection Rate, Compliance Rate
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
    page_title="ACGI Data Processing Dashboard",
    page_icon="📊",
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
        st.error("ไม่พบไฟล์ data_processing_stats.json")
        return None
    
    # โหลด compliance audit log
    try:
        with open('outputs/compliance_audit_log.json', 'r', encoding='utf-8') as f:
            data['compliance_audit'] = json.load(f)
    except FileNotFoundError:
        st.warning("ไม่พบไฟล์ compliance_audit_log.json")
        data['compliance_audit'] = {}

    # โหลด UBIF validation report
    try:
        with open('outputs/ubif_validation_report.json', 'r', encoding='utf-8') as f:
            data['ubif_validation'] = json.load(f)
    except FileNotFoundError:
        st.warning("ไม่พบไฟล์ ubif_validation_report.json")
        data['ubif_validation'] = {}

    # โหลด config เพื่อยืนยันโหมดการรันจริง
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            cfg_text = f.read()
        data['stream_clean_first'] = 'stream_clean_first: true' in cfg_text.lower()
    except FileNotFoundError:
        data['stream_clean_first'] = False
    
    # โหลด evaluation metrics
    try:
        with open('outputs/evaluation_metrics.json', 'r', encoding='utf-8') as f:
            data['evaluation_metrics'] = json.load(f)
    except FileNotFoundError:
        st.warning("ไม่พบไฟล์ evaluation_metrics.json")
        data['evaluation_metrics'] = {}
    
    return data

def calculate_metrics(data):
    """คำนวณเมตริกต่างๆ และ record flow ที่ต้องการ"""
    processing_stats = data['processing_stats']
    compliance_audit = data.get('compliance_audit', {})
    ubif_validation = data.get('ubif_validation', {})
    
    # เมตริกหลัก
    total_input_records = processing_stats.get('total_input_records', 0)
    valid_processed_records = processing_stats.get('valid_records', 0)
    invalid_processed_records = processing_stats.get('rejected_records', 0)

    cleaning_stats = processing_stats.get('cleaning_statistics', {})
    duplicates_removed = int(cleaning_stats.get('duplicates_removed', 0) or 0)
    test_admin_removed = int(cleaning_stats.get('test_accounts_removed', 0) or 0)
    bot_removed = int(cleaning_stats.get('bot_traffic_removed', 0) or 0)
    missing_service_id_removed = int(cleaning_stats.get('missing_service_id_removed', 0) or 0)
    stopword_removed = int(
        cleaning_stats.get('stopword_removed', cleaning_stats.get('irrelevant_keyword_removed', 0)) or 0
    )

    # Raw input (ประเมินจากสถิติ cleaning + validation เมื่อมี stream_clean_first)
    raw_input_records = int(
        processing_stats.get(
            'raw_input_records',
            total_input_records
            + duplicates_removed
            + test_admin_removed
            + bot_removed
            + missing_service_id_removed
            + stopword_removed
        )
        or 0
    )
    
    # คำนวณ rates
    rejection_rate = (invalid_processed_records / total_input_records * 100) if total_input_records > 0 else 0
    
    # Compliance Rate จาก audit log
    compliance_stats = compliance_audit.get('statistics', {})
    total_processed = compliance_stats.get('total_processed', 0)
    flagged_records = compliance_stats.get('flagged_records', 0)
    compliance_rate = ((total_processed - flagged_records) / total_processed * 100) if total_processed > 0 else 0

    # Algorithm 2 breakdown by rule
    violation_summary = ubif_validation.get('violation_summary', {})
    failed_alg2_by_rule = {
        'datetime format': 0,
        'latitude/longitude range': 0,
        'IP format': 0,
        'device field rule': 0,
        'serviceId / identifier rule': 0,
        'other rules': 0
    }

    for violation, count in violation_summary.items():
        v = str(violation).lower()
        c = int(count or 0)
        if 'iso_8601' in v or 'datetime' in v:
            failed_alg2_by_rule['datetime format'] += c
        elif 'w3c584' in v or 'latitude' in v or 'longitude' in v or 'location' in v:
            failed_alg2_by_rule['latitude/longitude range'] += c
        elif 'rfc_791_2460' in v or 'ip' in v:
            failed_alg2_by_rule['IP format'] += c
        elif 'ieee_802_1ar' in v or 'device' in v or 'operation' in v:
            failed_alg2_by_rule['device field rule'] += c
        elif 'iso_26324_2025' in v or 'serviceid' in v or 'identifier' in v or 'account' in v:
            failed_alg2_by_rule['serviceId / identifier rule'] += c
        else:
            failed_alg2_by_rule['other rules'] += c

    # Algorithm 3 breakdown by legal category
    attack_log = compliance_audit.get('attack_log', [])
    illegal_content_count = len(attack_log)
    flagged_by_law = {
        'privacy breach': 0,
        'illegal content': illegal_content_count,
        'invalid transaction format': 0,
        'consumer rights issue': 0
    }

    entered_alg2 = int(ubif_validation.get('total_records_processed', total_input_records) or 0)
    failed_alg2_total = int(ubif_validation.get('rejected_records', invalid_processed_records) or 0)
    passed_alg1 = max(entered_alg2, 0)
    entered_alg3 = int(total_processed or valid_processed_records)
    final_analytics_ready_output = processing_stats.get('session_statistics', {}).get('total_records', 0)

    flow = {
        'raw_input': raw_input_records,
        'removed_duplicate': duplicates_removed,
        'removed_test_admin': test_admin_removed,
        'removed_bot_crawler': bot_removed,
        'removed_missing_service_id': missing_service_id_removed,
        'removed_stopword_irrelevant': stopword_removed,
        'passed_algorithm_1': passed_alg1,
        'failed_algorithm_2_total': failed_alg2_total,
        'failed_algorithm_2_by_rule': failed_alg2_by_rule,
        'entered_algorithm_3': entered_alg3,
        'flagged_algorithm_3_by_law': flagged_by_law,
        'final_analytics_ready_output': final_analytics_ready_output
    }
    
    return {
        'total_input_records': total_input_records,
        'raw_input_records': raw_input_records,
        'valid_processed_records': valid_processed_records,
        'invalid_processed_records': invalid_processed_records,
        'rejection_rate': rejection_rate,
        'compliance_rate': compliance_rate,
        'train_records': processing_stats.get('train_records', 0),
        'test_records': processing_stats.get('test_records', 0),
        'total_sessions': processing_stats.get('session_statistics', {}).get('total_sessions', 0),
        'pdpa_anonymized': compliance_stats.get('pdpa_anonymized', 0),
        'threats_detected': compliance_stats.get('threats_detected', 0),
        'stream_clean_first': data.get('stream_clean_first', False),
        'flow': flow
    }


def create_record_flow_section(metrics):
    """แสดง Record Flow แบบครบทุก stage"""
    st.subheader("🔁 Record Flow (Full Breakdown)")

    flow = metrics['flow']
    rows = [
        ("Raw input", flow['raw_input']),
        ("Removed by duplicate", flow['removed_duplicate']),
        ("Removed by test/admin", flow['removed_test_admin']),
        ("Removed by bot/crawler", flow['removed_bot_crawler']),
        ("Removed by missing serviceId", flow['removed_missing_service_id']),
        ("Removed by stop-word / irrelevant keyword", flow['removed_stopword_irrelevant']),
        ("Passed Algorithm 1", flow['passed_algorithm_1']),
        ("Failed Algorithm 2 (total)", flow['failed_algorithm_2_total']),
        ("Entered Algorithm 3", flow['entered_algorithm_3']),
        ("Final analytics-ready output", flow['final_analytics_ready_output'])
    ]

    df_flow = pd.DataFrame(rows, columns=['Stage', 'Records'])
    st.dataframe(df_flow, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Raw Input", f"{flow['raw_input']:,}")
    with c2:
        st.metric("Passed Algorithm 1", f"{flow['passed_algorithm_1']:,}")
    with c3:
        st.metric("Final Analytics-ready", f"{flow['final_analytics_ready_output']:,}")

    st.markdown("### Failed Algorithm 2 by Rule")
    df_alg2 = pd.DataFrame(
        [(k, v) for k, v in flow['failed_algorithm_2_by_rule'].items()],
        columns=['Rule', 'Failed Records']
    )
    st.dataframe(df_alg2, use_container_width=True, hide_index=True)

    st.markdown("### Flagged by Algorithm 3 by Law")
    df_alg3 = pd.DataFrame(
        [(k, v) for k, v in flow['flagged_algorithm_3_by_law'].items()],
        columns=['Legal Group', 'Flagged Records']
    )
    st.dataframe(df_alg3, use_container_width=True, hide_index=True)


def create_pipeline_order_and_definitions(metrics):
    """ยืนยันลำดับ pipeline ที่รันจริง และนิยามคำสำคัญ"""
    st.subheader("🧭 Runtime Pipeline Order (Implementation)")

    if metrics.get('stream_clean_first', False):
        st.info(
            "Runtime mode: stream_clean_first = true\n\n"
            "Actual execution order: Streaming data cleaning (duplicate/test/bot/missing serviceId) "
            "→ UBIF validation (Algorithm 2) → Legal compliance (Algorithm 3) "
            "→ Parsing/Labeling/Sessionization/Split"
        )
    else:
        st.info(
            "Runtime mode: stream_clean_first = false\n\n"
            "Actual execution order: Batch data cleaning → UBIF validation (Algorithm 2) "
            "→ Legal compliance (Algorithm 3) → Parsing/Labeling/Sessionization/Split"
        )

    st.subheader("📘 Term Definitions")
    glossary = pd.DataFrame([
        ("valid", "Record passed UBIF validation with no violations."),
        ("rejected", "Record failed UBIF validation and was excluded from valid output."),
        ("removed", "Record dropped by cleaning filters and never entered next stage."),
        ("flagged", "Record marked with legal/security issue; in this pipeline still retained but annotated."),
        ("parsed", "Record transformed into extracted core fields and type-normalized format.")
    ], columns=['Term', 'Definition'])
    st.dataframe(glossary, use_container_width=True, hide_index=True)

def create_metrics_cards(metrics):
    """สร้างการ์ดแสดงเมตริกหลัก"""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="📋 Valid Processed Records",
            value=f"{metrics['valid_processed_records']:,}",
            delta=f"จาก {metrics['total_input_records']:,} records"
        )
    
    with col2:
        st.metric(
            label="❌ Invalid Processed Records",
            value=f"{metrics['invalid_processed_records']:,}",
            delta=f"{metrics['rejection_rate']:.2f}% rejection rate"
        )
    
    with col3:
        st.metric(
            label="📉 Rejection Rate",
            value=f"{metrics['rejection_rate']:.2f}%",
            delta=f"{metrics['invalid_processed_records']} ถูกปฏิเสธ"
        )
    
    with col4:
        st.metric(
            label="✅ Compliance Rate", 
            value=f"{metrics['compliance_rate']:.2f}%",
            delta=f"{metrics['pdpa_anonymized']:,} anonymized"
        )

def create_processing_overview(data, metrics):
    """สร้างภาพรวมการประมวลผล"""
    st.subheader("📊 Processing Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart สำหรับ Valid vs Invalid records
        fig_pie = go.Figure(data=[go.Pie(
            labels=['Valid Records', 'Invalid Records'],
            values=[metrics['valid_processed_records'], metrics['invalid_processed_records']],
            hole=0.4,
            marker_colors=['#2E8B57', '#DC143C']
        )])
        fig_pie.update_layout(
            title="Record Validation Status",
            font=dict(size=14)
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        # Bar chart สำหรับ Train/Test split
        fig_bar = go.Figure(data=[
            go.Bar(
                x=['Training Set', 'Test Set'],
                y=[metrics['train_records'], metrics['test_records']],
                marker_color=['#4682B4', '#FF6347'],
                text=[f"{metrics['train_records']:,}", f"{metrics['test_records']:,}"],
                textposition='auto'
            )
        ])
        fig_bar.update_layout(
            title="Train/Test Data Split",
            yaxis_title="Number of Records",
            font=dict(size=14)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

def create_interest_distribution(data):
    """สร้างกราฟแสดงการแจกแจงของ Interest"""
    st.subheader("🎯 Interest Distribution")
    
    processing_stats = data['processing_stats']
    train_interest = processing_stats.get('train_interest_distribution', {})
    test_interest = processing_stats.get('test_interest_distribution', {})
    
    # สร้าง DataFrame สำหรับการแสดงผล
    df_interest = pd.DataFrame({
        'Dataset': ['Training', 'Training', 'Test', 'Test'],
        'Interest Type': ['Interest', 'No Interest', 'Interest', 'No Interest'],
        'Count': [
            train_interest.get('interest', 0),
            train_interest.get('no_interest', 0),
            test_interest.get('interest', 0),
            test_interest.get('no_interest', 0)
        ]
    })
    
    fig_interest = px.bar(
        df_interest, 
        x='Dataset', 
        y='Count', 
        color='Interest Type',
        title='Interest Distribution in Train/Test Sets',
        color_discrete_map={'Interest': '#2E8B57', 'No Interest': '#DC143C'}
    )
    fig_interest.update_layout(font=dict(size=14))
    st.plotly_chart(fig_interest, use_container_width=True)
    
    # แสดงเปอร์เซ็นต์
    col1, col2 = st.columns(2)
    with col1:
        train_total = train_interest.get('interest', 0) + train_interest.get('no_interest', 0)
        train_interest_rate = (train_interest.get('interest', 0) / train_total * 100) if train_total > 0 else 0
        st.metric("🎯 Training Interest Rate", f"{train_interest_rate:.2f}%")
    
    with col2:
        test_total = test_interest.get('interest', 0) + test_interest.get('no_interest', 0)
        test_interest_rate = (test_interest.get('interest', 0) / test_total * 100) if test_total > 0 else 0
        st.metric("🎯 Test Interest Rate", f"{test_interest_rate:.2f}%")

def create_processing_timeline(data):
    """สร้างแผนภูมิแสดงเวลาการประมวลผลแต่ละขั้นตอน"""
    st.subheader("⏱️ Processing Timeline")
    
    step_durations = data['processing_stats'].get('step_durations_seconds', {})
    
    if step_durations:
        # แปลง step names เป็นภาษาไทย
        step_names_th = {
            'step_1_data_cleaning': 'Data Cleaning',
            'step_2_ubif_validation': 'UBIF Validation',
            'step_3_legal_compliance': 'Legal Compliance',
            'step_4_interest_labeling': 'Interest Labeling',
            'step_5_sessionization': 'Sessionization',
            'step_6_temporal_split': 'Temporal Split',
            'step_7_save_outputs': 'Saving Outputs'
        }
        
        steps = []
        durations = []
        for step, duration in step_durations.items():
            steps.append(step_names_th.get(step, step))
            durations.append(duration)
        
        fig_timeline = go.Figure([go.Bar(
            x=durations,
            y=steps,
            orientation='h',
            marker_color='#4682B4',
            text=[f"{d:.2f}s" for d in durations],
            textposition='auto'
        )])
        
        fig_timeline.update_layout(
            title="Processing Time by Step",
            xaxis_title="Duration (seconds)",
            font=dict(size=14),
            height=400
        )
        
        st.plotly_chart(fig_timeline, use_container_width=True)
        
        # แสดงสถิติเวลา
        total_time = sum(durations)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("⏱️ Total Processing Time", f"{total_time:.2f}s")
        with col2:
            st.metric("📈 Average Step Time", f"{np.mean(durations):.2f}s")
        with col3:
            longest_step = steps[np.argmax(durations)]
            st.metric("🔍 Longest Step", longest_step)

def create_evaluation_metrics(data):
    """สร้างแผนภูมิแสดงผลการประเมิน"""
    st.subheader("🎯 Model Evaluation Metrics")
    
    eval_metrics = data.get('evaluation_metrics', {})
    test_metrics = eval_metrics.get('test_metrics', {})
    
    if test_metrics:
        col1, col2 = st.columns(2)
        
        with col1:
            # Confusion Matrix
            confusion_matrix = test_metrics.get('confusion_matrix', [[0, 0], [0, 0]])
            tn, fp, fn, tp = confusion_matrix[0][0], confusion_matrix[0][1], confusion_matrix[1][0], confusion_matrix[1][1]
            
            fig_cm = go.Figure(data=go.Heatmap(
                z=[[tn, fp], [fn, tp]],
                x=['Predicted No', 'Predicted Yes'],
                y=['Actual No', 'Actual Yes'],
                text=[[f'TN: {tn}', f'FP: {fp}'], [f'FN: {fn}', f'TP: {tp}']],
                texttemplate="%{text}",
                colorscale='Blues'
            ))
            fig_cm.update_layout(title="Confusion Matrix", font=dict(size=14))
            st.plotly_chart(fig_cm, use_container_width=True)
        
        with col2:
            # Performance Metrics
            metrics_names = ['Accuracy', 'Precision', 'Recall', 'F1-Score', 'ROC-AUC']
            metrics_values = [
                test_metrics.get('accuracy', 0),
                test_metrics.get('precision', 0),
                test_metrics.get('recall', 0),
                test_metrics.get('f1_score', 0),
                test_metrics.get('roc_auc', 0)
            ]
            
            fig_metrics = go.Figure([go.Bar(
                x=metrics_names,
                y=metrics_values,
                marker_color=['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57'],
                text=[f"{v:.3f}" for v in metrics_values],
                textposition='auto'
            )])
            
            fig_metrics.update_layout(
                title="Model Performance Metrics",
                yaxis_title="Score",
                yaxis=dict(range=[0, 1]),
                font=dict(size=14)
            )
            st.plotly_chart(fig_metrics, use_container_width=True)

def create_session_statistics(data):
    """สร้างสถิติเซสชัน"""
    st.subheader("🔄 Session Statistics")
    
    session_stats = data['processing_stats'].get('session_statistics', {})
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📊 Total Sessions", f"{session_stats.get('total_sessions', 0):,}")
    
    with col2:
        st.metric("📈 Avg Session Length", f"{session_stats.get('avg_session_length', 0):.2f}")
    
    with col3:
        st.metric("📉 Min Session Length", f"{session_stats.get('min_session_length', 0)}")
    
    with col4:
        st.metric("📊 Max Session Length", f"{session_stats.get('max_session_length', 0)}")

def main():
    """ฟังก์ชันหลักของ Dashboard"""
    
    # Header
    st.title("📊 ACGI Data Processing Dashboard")
    st.markdown("### PHASE 1: DATA PROCESSING PIPELINE และ EVALUATION")
    
    # โหลดข้อมูล
    with st.spinner("กำลังโหลดข้อมูล..."):
        data = load_data()
    
    if data is None:
        st.stop()
    
    # คำนวณเมตริก
    metrics = calculate_metrics(data)
    
    # แสดงข้อมูลเมื่อไหร่สร้าง
    generated_at = data['processing_stats'].get('generated_at', 'Unknown')
    if generated_at != 'Unknown':
        try:
            gen_time = datetime.fromisoformat(generated_at)
            st.info(f"📅 ข้อมูลสร้างเมื่อ: {gen_time.strftime('%d/%m/%Y %H:%M:%S')}")
        except:
            st.info(f"📅 ข้อมูลสร้างเมื่อ: {generated_at}")
    
    # Sidebar สำหรับตัวเลือก
    st.sidebar.title("Dashboard Options")
    show_metrics = st.sidebar.checkbox("แสดงเมตริกหลัก", True)
    show_overview = st.sidebar.checkbox("แสดงภาพรวมการประมวลผล", True)
    show_interest = st.sidebar.checkbox("แสดงการแจกแจง Interest", True)
    show_timeline = st.sidebar.checkbox("แสดงเวลาการประมวลผล", True)
    show_evaluation = st.sidebar.checkbox("แสดงผลการประเมินโมเดล", True)
    show_sessions = st.sidebar.checkbox("แสดงสถิติเซสชัน", True)
    show_record_flow = st.sidebar.checkbox("แสดง Record Flow แบบละเอียด", True)
    show_pipeline_definitions = st.sidebar.checkbox("แสดงลำดับ Pipeline และนิยามคำ", True)
    
    # แสดงเนื้อหาตามตัวเลือก
    if show_metrics:
        st.markdown("---")
        create_metrics_cards(metrics)
    
    if show_overview:
        st.markdown("---")
        create_processing_overview(data, metrics)
    
    if show_interest:
        st.markdown("---")
        create_interest_distribution(data)
    
    if show_timeline:
        st.markdown("---")
        create_processing_timeline(data)
    
    if show_evaluation and 'evaluation_metrics' in data:
        st.markdown("---")
        create_evaluation_metrics(data)
    
    if show_sessions:
        st.markdown("---")
        create_session_statistics(data)

    if show_record_flow:
        st.markdown("---")
        create_record_flow_section(metrics)

    if show_pipeline_definitions:
        st.markdown("---")
        create_pipeline_order_and_definitions(metrics)
    
    # Footer
    st.markdown("---")
    st.markdown("**🔧 ACGI Project Dashboard** | Powered by Streamlit")

if __name__ == "__main__":
    main()