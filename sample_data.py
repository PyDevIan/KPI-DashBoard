# Project: streamlit_kpi_dashboard
# Directory:
# ├── data/
# ├── metrics.py
# ├── app.py
# ├── requirements.txt
# └── README.md

# New: data_csvs.zip generator script
# Use this script to generate sample CSVs for each KPI and package them into a zip.

# run this with: python generate_sample_data.py

import pandas as pd
import zipfile
from io import BytesIO

# Sample data for each CSV
sample_data = {
    'apps.csv': pd.DataFrame([
        {'app_id': 1, 'app_name': 'AutoReport', 'month': '2025-06', 'time_before_hrs': 10, 'time_after_hrs': 2, 'frequency_per_month': 20, 'dev_hrs': 15},
        {'app_id': 2, 'app_name': 'InvoiceGen', 'month': '2025-06', 'time_before_hrs': 8, 'time_after_hrs': 1, 'frequency_per_month': 10, 'dev_hrs': 10},
    ]),
    'data_collection.csv': pd.DataFrame([
        {'proc_id': 1, 'proc_name': 'SurveyCollector', 'month': '2025-06', 'data_vol_before': 1000, 'data_vol_after': 1500},
        {'proc_id': 2, 'proc_name': 'LogIngest', 'month': '2025-06', 'data_vol_before': 5000, 'data_vol_after': 7000},
    ]),
    'process_speed.csv': pd.DataFrame([
        {'proc_id': 1, 'proc_name': 'ReportGen', 'month': '2025-06', 'time_before_hrs': 5, 'time_after_hrs': 1},
        {'proc_id': 2, 'proc_name': 'DataCleanup', 'month': '2025-06', 'time_before_hrs': 3, 'time_after_hrs': 0.5},
    ]),
    'dev_speed.csv': pd.DataFrame([
        {'app_id': 1, 'app_name': 'AutoReport', 'idea_date': '2025-06-01', 'deploy_date': '2025-06-05'},
        {'app_id': 2, 'app_name': 'SurveyCollector', 'idea_date': '2025-06-10', 'deploy_date': '2025-06-12'},
    ]),
    'mentoring.csv': pd.DataFrame([
        {'session_id': 1, 'date': '2025-06-15', 'mentor_hrs': 2, 'team_time_saved_hrs': 5},
        {'session_id': 2, 'date': '2025-06-20', 'mentor_hrs': 3, 'team_time_saved_hrs': 10},
    ]),
    'tool_engagement.csv': pd.DataFrame([
        {'date': '2025-06-30', 'active_sessions': 120, 'api_calls': 450},
        {'date': '2025-07-31', 'active_sessions': 150, 'api_calls': 500},
    ]),
    'tickets.csv': pd.DataFrame([
        {'ticket_id': 101, 'date_closed': '2025-06-10', 'closed_successfully': 1},
        {'ticket_id': 102, 'date_closed': '2025-06-12', 'closed_successfully': 0},
    ]),
    'issues.csv': pd.DataFrame([
        {'issue_id': 201, 'date_closed': '2025-06-05', 'type': 'PR'},
        {'issue_id': 202, 'date_closed': '2025-06-08', 'type': 'bug'},
    ]),
    'learning.csv': pd.DataFrame([
        {'date': '2025-06-01', 'learning_hrs': 10, 'applied_hrs': 4},
        {'date': '2025-06-15', 'learning_hrs': 8, 'applied_hrs': 6},
    ]),
}

# Create in-memory zip
buffer = BytesIO()
with zipfile.ZipFile(buffer, 'w') as zf:
    for filename, df in sample_data.items():
        zf.writestr(filename, df.to_csv(index=False))
buffer.seek(0)

# Write to file
with open('data_csvs.zip', 'wb') as f:
    f.write(buffer.getvalue())

print("Generated data_csvs.zip with sample CSVs.")

import pandas as pd
from typing import Dict, Callable

# Registry for KPI computation functions
KPI_FUNCTIONS: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {}

def register_kpi(name: str):
    """Decorator to register a KPI computation function by name"""
    def decorator(func: Callable[[pd.DataFrame], pd.DataFrame]):
        KPI_FUNCTIONS[name] = func
        return func
    return decorator

@register_kpi("time_saved")
def compute_time_saved(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate per-app and total monthly time saved and ROI.
    Expects columns: month, time_before_hrs, time_after_hrs, frequency_per_month, dev_hrs
    """
    df = df.copy()
    df['time_saved'] = (df['time_before_hrs'] - df['time_after_hrs']) * df['frequency_per_month']
    df['roi'] = df['time_saved'] / df['dev_hrs']
    result = df.groupby('month').agg(
        total_saved=('time_saved', 'sum'),
        avg_roi=('roi', 'mean')
    ).reset_index()
    return result

@register_kpi("process_speed_improvement")
def compute_process_speed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate process speed improvement percentage.
    Expects columns: month, time_before_hrs, time_after_hrs
    """
    df = df.copy()
    df['improvement_pct'] = (df['time_before_hrs'] - df['time_after_hrs']) / df['time_before_hrs'] * 100
    result = df.groupby('month').agg(
        avg_improvement=('improvement_pct', 'mean')
    ).reset_index()
    return result

# TODO: register other KPIs similarly, e.g., data_collection_efficiency, mentoring_roi, etc.


def load_kpi(csv_file, parse_dates=None) -> pd.DataFrame:
    """Load CSV file as DataFrame, parsing specified date columns"""
    default_dates = ['month', 'date', 'date_closed', 'idea_date', 'deploy_date']
    parse_dates = parse_dates or default_dates
    return pd.read_csv(csv_file, parse_dates=parse_dates)


def compute_kpi(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Compute a registered KPI from its DataFrame"""
    if name not in KPI_FUNCTIONS:
        raise ValueError(f"KPI '{name}' is not registered. Available: {list(KPI_FUNCTIONS.keys())}")
    return KPI_FUNCTIONS[name](df)


def list_kpis() -> list:
    """Return the list of registered KPI names"""
    return list(KPI_FUNCTIONS.keys())


# app.py
import streamlit as st
import pandas as pd
import metrics
from datetime import date

st.set_page_config(page_title="Career KPI Dashboard", layout="wide")

# Sidebar: Upload CSVs dynamically based on registered KPIs
st.sidebar.header("Upload KPI Data")
uploads = {}
for kpi in metrics.list_kpis():
    uploads[kpi] = st.sidebar.file_uploader(f"{kpi.replace('_', ' ').title()} CSV", type=["csv"], key=kpi)

# Sidebar: Date range filter\ nst.sidebar.header("Date Range")
start_date = st.sidebar.date_input("Start date", value=date.today().replace(day=1))
end_date = st.sidebar.date_input("End date", value=date.today())

# Sidebar: Select which KPIs to display
selected_kpis = st.sidebar.multiselect(
    "Select KPIs to show", metrics.list_kpis(), default=metrics.list_kpis())

st.title("🏆 Personal Career KPI Dashboard")

# Metric cards for latest KPI values
cols = st.columns(len(selected_kpis) or 1)
for idx, kpi in enumerate(selected_kpis):
    csv_file = uploads[kpi]
    if csv_file:
        df_raw = metrics.load_kpi(csv_file)
        df_kpi = metrics.compute_kpi(kpi, df_raw)
        # Filter by date range
        mask = (df_kpi['month'] >= pd.to_datetime(start_date)) & (df_kpi['month'] <= pd.to_datetime(end_date))
        df_kpi = df_kpi.loc[mask]
        if not df_kpi.empty:
            latest = df_kpi.sort_values('month').iloc[-1]
            # Assumes primary metric is the second column
            val = latest.iloc[1]
            cols[idx].metric(label=kpi.replace('_', ' ').title(), value=f"{val:.2f}")
        else:
            cols[idx].info("No data in range")
    else:
        cols[idx].warning("Upload CSV to visualize")

# KPI Trends
st.header("KPI Trends")
for kpi in selected_kpis:
    csv_file = uploads[kpi]
    if not csv_file:
        continue
    df_raw = metrics.load_kpi(csv_file)
    df_kpi = metrics.compute_kpi(kpi, df_raw).set_index('month')
    st.subheader(kpi.replace('_', ' ').title())
    st.line_chart(df_kpi)

# Placeholder for detailed views and future KPIs
st.markdown("---")
st.write("More detailed KPI breakdowns coming soon...")

# End of app.py
