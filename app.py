# app.py
import streamlit as st
import metrics
import pandas as pd
import glob, os
from datetime import date, datetime

st.set_page_config(page_title="Career KPI Dashboard", layout="wide")

DATA_DIR = "data"

# --- CSV Schema Map (for data-entry form) ---
CSV_SCHEMAS = {
    # Apps: merged apps + dev speed
    "apps": [
        "app_id",
        "app_name",
        "app_type",
        "idea_date",
        "deploy_date",
        "month",
        "time_before_hrs",
        "time_after_hrs",
        "frequency_per_month",
    ],
    # Data Collection: info gain + speed (time in seconds)
    "data_collection": [
        "proc_id",
        "proc_name",
        "month",
        "fields_before",
        "fields_after",
        "time_before_sec",
        "time_after_sec",
    ],
    # Mentoring: dept + mentoring type
    "mentoring": [
        "session_id",
        "date",
        "dept",
        "mentoring_type",
        "mentor_hrs",
        "team_time_saved_hrs",
    ],
    # AI Engagement: dept usage
    "ai_engagement": ["month", "dept", "active_users", "ai_calls", "survey_score"],
    # Project Mgmt: MVP timelines
    "project_mgmt": [
        "project_name",
        "dept",
        "start_date",
        "mvp_target_date",
        "mvp_actual_date",
    ],
    # Tickets & Issues
    "tickets": ["ticket_id", "date_closed"],
    "issues": ["issue_id", "date_closed", "type"],
    # Learning: efficiency + profit
    "learning": [
        "date",
        "skill",
        "implementations",
        "usages",
        "learning_hrs",
        "applied_hrs",
        "profit_over_legacy_pct",
    ],
    # Time Management: weekly allocation
    "time_mgmt": [
        "week_start",
        "kw",
        "development",
        "debugging_tickets",
        "mentoring",
        "devops",
        "project_management",
        "meetings",
    ],
}

DEPT_OPTIONS = [
    "RM",
    "PD",
    "Logistics",
    "Procurement",
    "Production",
    "Production-olives",
    "QA",
    "QC-prod",
    "QC-olives",
    "RND",
    "BIO",
    "Sales",
    "Finance",
    "IT",
    "Financial Analysis & ERP",
]
MENTORING_TYPES = ["prompt_eng", "nocode_guidance", "ai_assistant_util"]
APP_TYPES = {
    "Simple Data Collection/Procedure": "simple",
    "AI Full App": "ai_full",
    "AI Assistant App": "ai_assistant",
}

# --- KPI Meta / Names ---
KPI_META = {
    k: metrics.get_kpi_meta(k) for k in metrics.list_kpis() if metrics.get_kpi_meta(k)
}
DISPLAY_NAME_MAP = {k: v["display_name"] for k, v in KPI_META.items()}
INVERSE_DISPLAY_NAME_MAP = {v: k for k, v in DISPLAY_NAME_MAP.items()}

# --- Discover CSVs in /data ---
uploads = {}
for fp in glob.glob(os.path.join(DATA_DIR, "*.csv")):
    key = os.path.splitext(os.path.basename(fp))[0]
    if key in metrics.list_kpis():
        uploads[key] = fp

# --- Sidebar filters ---
st.sidebar.title("Data Status & Filters")
start_date = st.sidebar.date_input("Start Date", value=date.today().replace(day=1))
end_date = st.sidebar.date_input("End Date", value=date.today())

existing_kpi_labels = [
    DISPLAY_NAME_MAP[k] for k in uploads.keys() if k in DISPLAY_NAME_MAP
]
selected_labels = st.sidebar.multiselect(
    "Select KPIs to Display", existing_kpi_labels, default=existing_kpi_labels
)
selected_kpis = [
    INVERSE_DISPLAY_NAME_MAP[label]
    for label in selected_labels
    if INVERSE_DISPLAY_NAME_MAP[label] in uploads
]

st.title("🏆 Personal Career KPI Dashboard")

if not selected_kpis:
    st.subheader("📊 KPI Reference Table")

    kpi_data = []
    for key, meta in metrics.KPI_META.items():
        kpi_data.append(
            {
                "KPI Name": meta.get("display_name", key),
                "What It Measures": meta.get("description", ""),
                "Value / Unit": meta.get("unit", ""),
                "Data Source (CSV)": meta.get("source_csv", ""),
            }
        )
    df_kpi_meta = pd.DataFrame(kpi_data)
    st.dataframe(df_kpi_meta)

    st.stop()  # Prevents the rest of the dashboard from rendering

# --- Metric cards ---
cols = st.columns(len(selected_kpis))
for idx, kpi in enumerate(selected_kpis):
    col = cols[idx]
    df_raw = metrics.load_kpi(uploads[kpi])
    df_kpi = metrics.compute_kpi(kpi, df_raw)

    meta = metrics.get_kpi_meta(kpi)
    label = meta.get("display_name", kpi.replace("_", " ").title())
    unit = meta.get("unit", "")
    help_ = meta.get("description", "")

    # Date-range filter for monthly results
    if "month" in df_kpi.columns:
        df_kpi["month"] = pd.to_datetime(df_kpi["month"], errors="coerce")
        df_kpi = df_kpi[
            (df_kpi["month"] >= pd.to_datetime(start_date))
            & (df_kpi["month"] <= pd.to_datetime(end_date))
        ]

    # Tickets: total in selected date range
    if kpi == "tickets":
        if "date_closed" in df_raw.columns:
            f = df_raw.copy()
            f["date_closed"] = pd.to_datetime(f["date_closed"], errors="coerce")
            f = f[
                (f["date_closed"] >= pd.to_datetime(start_date))
                & (f["date_closed"] <= pd.to_datetime(end_date))
            ]
            value = int(len(f))
            col.metric(label=label, value=f"{value:.0f} {unit}", help=help_)
        else:
            col.info("No records")
        continue

    # Issues: total in range
    if kpi == "issues":
        if "date_closed" in df_raw.columns:
            f = df_raw.copy()
            f["date_closed"] = pd.to_datetime(f["date_closed"], errors="coerce")
            f = f[
                (f["date_closed"] >= pd.to_datetime(start_date))
                & (f["date_closed"] <= pd.to_datetime(end_date))
            ]
            total_issues = int(len(f))
            col.metric(label=label, value=f"{total_issues:.0f} {unit}", help=help_)
        else:
            col.info("No records")
        continue

    # Data Collection: range-avg weighted info gain (%)
    if kpi == "data_collection" and not df_kpi.empty:
        value = df_kpi["weighted_info_gain_pct"].mean(skipna=True)
        col.metric(
            label=f"{label} (Info Gain)",
            value=f"{value:.2f} %",
            help="Weighted by fields_before; higher is better",
        )
        continue

    # Apps: total hours saved in range + Avg Dev Speed (all types)
    if kpi == "apps":
        total_hours_saved = 0.0
        if not df_kpi.empty and "total_saved" in df_kpi.columns:
            total_hours_saved = float(df_kpi["total_saved"].sum())
        col.metric(
            label=f"{label} – Total Saved",
            value=f"{total_hours_saved:.1f} hours",
            help="Sum of (time_before - time_after) * frequency across apps in range",
        )

        # Overall Avg Dev Speed across all types (days) — based on deploy_date in range
        if set(["deploy_date", "idea_date"]).issubset(df_raw.columns):
            speed = df_raw.copy()
            speed["deploy_date"] = pd.to_datetime(speed["deploy_date"], errors="coerce")
            speed["idea_date"] = pd.to_datetime(speed["idea_date"], errors="coerce")
            speed = speed.dropna(subset=["deploy_date", "idea_date"])
            speed = speed[
                (speed["deploy_date"] >= pd.to_datetime(start_date))
                & (speed["deploy_date"] <= pd.to_datetime(end_date))
            ]
            if not speed.empty:
                speed["dev_days"] = (speed["deploy_date"] - speed["idea_date"]).dt.days
                avg_days = float(speed["dev_days"].mean())
                col.metric(
                    label=f"Avg Dev Speed (All Types)", value=f"{avg_days:.1f} days"
                )
        continue

    # Mentoring: ROI in range (use raw dates)
    if kpi == "mentoring":
        if set(["date", "mentor_hrs", "team_time_saved_hrs"]).issubset(df_raw.columns):
            m = df_raw.copy()
            m["date"] = pd.to_datetime(m["date"], errors="coerce")
            m = m[
                (m["date"] >= pd.to_datetime(start_date))
                & (m["date"] <= pd.to_datetime(end_date))
            ]
            if not m.empty:
                mentor_hrs = float(
                    pd.to_numeric(m["mentor_hrs"], errors="coerce").sum()
                )
                team_saved = float(
                    pd.to_numeric(m["team_time_saved_hrs"], errors="coerce").sum()
                )
                roi = (team_saved / mentor_hrs) if mentor_hrs > 0 else 0.0
                col.metric(label="Mentoring ROI", value=f"{roi:.2f} ratio", help=help_)
            else:
                col.info("No records")
        continue

    # AI Engagement: total ai_calls in range (summed from monthly totals)
    if kpi == "ai_engagement":
        if set(["month", "dept"]).issubset(df_raw.columns):
            eng_raw = df_raw.copy()
            eng_raw["month"] = pd.to_datetime(eng_raw["month"], errors="coerce")
            eng_raw = eng_raw[
                (eng_raw["month"] >= pd.to_datetime(start_date))
                & (eng_raw["month"] <= pd.to_datetime(end_date))
            ]
            if not eng_raw.empty:
                total_calls = int(
                    pd.to_numeric(eng_raw["ai_calls"], errors="coerce").sum()
                )
                col.metric(
                    label="Total AI Calls", value=f"{total_calls} events", help=help_
                )
            else:
                col.info("No records")
        continue

    # Project Mgmt: projects running in range
    if kpi == "project_mgmt":
        pm = df_raw.copy()
        for c in ["start_date", "mvp_target_date", "mvp_actual_date"]:
            pm[c] = pd.to_datetime(pm[c], errors="coerce")
        # Running if started before end_date and not finished before start_date
        running = pm[
            (pm["start_date"] <= pd.to_datetime(end_date))
            & (
                (pm["mvp_actual_date"].isna())
                | (pm["mvp_actual_date"] >= pd.to_datetime(start_date))
            )
        ]
        col.metric(label="Projects Running", value=f"{len(running)}", help=help_)
        continue

    # Time Management: average Dev% in range
    if kpi == "time_mgmt":
        tm = metrics.compute_kpi("time_mgmt", df_raw)
        if "week_start" in tm.columns:
            tm = tm[
                (tm["week_start"] >= pd.to_datetime(start_date))
                & (tm["week_start"] <= pd.to_datetime(end_date))
            ]
        if tm.empty:
            col.info("No records")
        else:
            if "development_pct" in tm.columns:
                dev_focus = float(
                    pd.to_numeric(tm["development_pct"], errors="coerce").mean()
                )
                col.metric(
                    label="Dev Focus (avg)",
                    value=f"{dev_focus:.1f} %",
                    help="Average share of weekly hours spent on Development in the selected date range",
                )
            else:
                total_hours = float(
                    pd.to_numeric(tm["total_hours"], errors="coerce").sum()
                )
                col.metric(
                    label="Total Hours (range)", value=f"{total_hours:.1f} hours"
                )
        continue

    # Generic fallback
    if df_kpi.empty:
        col.info("No records")
        continue
    metric_cols = [c for c in df_kpi.columns if c != "month"]
    if not metric_cols:
        col.info("No metric columns")
        continue
    if "month" in df_kpi.columns and not df_kpi.empty:
        latest = df_kpi.sort_values("month").iloc[-1]
        value = latest[metric_cols[0]]
    else:
        value = df_kpi[metric_cols[0]].iloc[-1]
    fmt = "{:.0f}" if unit in ("count",) else "{:.2f}"
    col.metric(label=label, value=f"{fmt.format(value)} {unit}", help=help_)

# --- Trends & Details ---
st.header("Trends & Details")
for kpi in selected_kpis:
    df_raw = metrics.load_kpi(uploads[kpi])
    meta = metrics.get_kpi_meta(kpi)
    st.subheader(meta.get("display_name", kpi.replace("_", " ").title()))
    st.caption(meta.get("description", ""))

    # Tickets
    if kpi == "tickets":
        if "date_closed" in df_raw.columns:
            f = df_raw.copy()
            f["date_closed"] = pd.to_datetime(f["date_closed"], errors="coerce")
            f = f[
                (f["date_closed"] >= pd.to_datetime(start_date))
                & (f["date_closed"] <= pd.to_datetime(end_date))
            ]
            st.metric(label="Total in Range", value=int(len(f)))
            st.dataframe(f.sort_values("date_closed", ascending=False).head(50))
        continue

    # Issues
    if kpi == "issues":
        if set(["date_closed", "type"]).issubset(df_raw.columns):
            f = df_raw.copy()
            f["date_closed"] = pd.to_datetime(f["date_closed"], errors="coerce")
            f = f[
                (f["date_closed"] >= pd.to_datetime(start_date))
                & (f["date_closed"] <= pd.to_datetime(end_date))
            ]
            per_type = f.groupby("type").size().reset_index(name="count")
            st.metric(label="Total in Range", value=int(len(f)))
            if not per_type.empty:
                st.bar_chart(per_type.set_index("type"))
                st.dataframe(per_type.sort_values("count", ascending=False))
            else:
                st.info("No issues in selected range")
        continue

    # Data Collection
    if kpi == "data_collection":
        df_kpi = metrics.compute_kpi(kpi, df_raw)
        if not df_kpi.empty:
            df_kpi["month"] = pd.to_datetime(df_kpi["month"], errors="coerce")
            df_kpi = df_kpi[
                (df_kpi["month"] >= pd.to_datetime(start_date))
                & (df_kpi["month"] <= pd.to_datetime(end_date))
            ]
            df_kpi["avg_speed_delta_hrs"] = df_kpi["avg_speed_delta_sec"] / 3600.0
            st.line_chart(
                df_kpi.set_index("month")[
                    ["weighted_info_gain_pct", "avg_speed_impr_pct"]
                ]
            )
            st.dataframe(
                df_kpi[
                    [
                        "month",
                        "avg_info_gain_pct",
                        "weighted_info_gain_pct",
                        "avg_speed_impr_pct",
                        "avg_speed_delta_hrs",
                        "total_fields_added",
                    ]
                ]
                .sort_values("month")
                .rename(columns={"avg_speed_delta_hrs": "avg_speed_delta (hrs)"})
            )
        else:
            st.info("No records")
        continue

    # Apps
    if kpi == "apps":
        # Trend: monthly total saved
        df_apps = metrics.compute_kpi("apps", df_raw)
        if not df_apps.empty:
            df_apps["month"] = pd.to_datetime(df_apps["month"], errors="coerce")
            df_apps = df_apps[
                (df_apps["month"] >= pd.to_datetime(start_date))
                & (df_apps["month"] <= pd.to_datetime(end_date))
            ]
            st.line_chart(
                df_apps.set_index("month")[["total_saved"]].rename(
                    columns={"total_saved": "Total Saved (hrs)"}
                )
            )
        else:
            st.info("No records")

        # Per-type avg dev speed (days)
        if set(["deploy_date", "idea_date", "app_type"]).issubset(df_raw.columns):
            sp = df_raw.copy()
            sp["deploy_date"] = pd.to_datetime(sp["deploy_date"], errors="coerce")
            sp["idea_date"] = pd.to_datetime(sp["idea_date"], errors="coerce")
            sp = sp.dropna(subset=["deploy_date", "idea_date", "app_type"])
            sp = sp[
                (sp["deploy_date"] >= pd.to_datetime(start_date))
                & (sp["deploy_date"] <= pd.to_datetime(end_date))
            ]
            if not sp.empty:
                sp["dev_days"] = (sp["deploy_date"] - sp["idea_date"]).dt.days
                type_labels = {
                    "simple": "Simple Data Collection/Procedure",
                    "ai_full": "AI Full App",
                    "ai_assistant": "AI Assistant App",
                }
                sp["app_type_label"] = (
                    sp["app_type"].map(type_labels).fillna(sp["app_type"])
                )
                per_type = sp.groupby("app_type_label", as_index=False).agg(
                    avg_dev_days=("dev_days", "mean")
                )
                st.subheader("Avg Dev Speed by App Type (days)")
                st.bar_chart(per_type.set_index("app_type_label"))
                st.dataframe(per_type.sort_values("avg_dev_days"))
            else:
                st.info("No deployments in range")
        continue

    # Mentoring
    if kpi == "mentoring":
        if set(
            ["date", "dept", "mentoring_type", "mentor_hrs", "team_time_saved_hrs"]
        ).issubset(df_raw.columns):
            m = df_raw.copy()
            m["date"] = pd.to_datetime(m["date"], errors="coerce")
            m = m[
                (m["date"] >= pd.to_datetime(start_date))
                & (m["date"] <= pd.to_datetime(end_date))
            ]

            if not m.empty:
                m["mentor_hrs"] = pd.to_numeric(m["mentor_hrs"], errors="coerce")
                m["team_time_saved_hrs"] = pd.to_numeric(
                    m["team_time_saved_hrs"], errors="coerce"
                )

                per_dept = m.groupby("dept", as_index=False).agg(
                    mentor_hrs=("mentor_hrs", "sum"),
                    team_saved=("team_time_saved_hrs", "sum"),
                )
                per_dept["roi"] = per_dept.apply(
                    lambda r: (
                        (r["team_saved"] / r["mentor_hrs"])
                        if r["mentor_hrs"] > 0
                        else 0
                    ),
                    axis=1,
                )
                st.subheader("Per-Department Mentoring")
                if not per_dept.empty:
                    st.bar_chart(
                        per_dept.set_index("dept")[["mentor_hrs", "team_saved"]]
                    )
                    st.dataframe(per_dept.sort_values("roi", ascending=False))

                per_type = m.groupby("mentoring_type", as_index=False).agg(
                    mentor_hrs=("mentor_hrs", "sum"),
                    team_saved=("team_time_saved_hrs", "sum"),
                )
                per_type["roi"] = per_type.apply(
                    lambda r: (
                        (r["team_saved"] / r["mentor_hrs"])
                        if r["mentor_hrs"] > 0
                        else 0
                    ),
                    axis=1,
                )
                st.subheader("Per-Type Mentoring")
                st.dataframe(per_type.sort_values("roi", ascending=False))
            else:
                st.info("No mentoring sessions in selected range")
        continue

    # AI Engagement
    if kpi == "ai_engagement":
        if set(["month", "dept"]).issubset(df_raw.columns):
            eng = df_raw.copy()
            eng["month"] = pd.to_datetime(eng["month"], errors="coerce")
            eng = eng[
                (eng["month"] >= pd.to_datetime(start_date))
                & (eng["month"] <= pd.to_datetime(end_date))
            ]
            if not eng.empty:
                per_dept = eng.groupby("dept", as_index=False).agg(
                    active_users=("active_users", "sum"),
                    ai_calls=("ai_calls", "sum"),
                    avg_survey=("survey_score", "mean"),
                )
                st.bar_chart(per_dept.set_index("dept")[["ai_calls"]])
                st.dataframe(per_dept.sort_values("ai_calls", ascending=False))
            else:
                st.info("No engagement records in range")
        continue

    # Project Mgmt
    if kpi == "project_mgmt":
        pm = df_raw.copy()
        for c in ["start_date", "mvp_target_date", "mvp_actual_date"]:
            pm[c] = pd.to_datetime(pm[c], errors="coerce")
        running = pm[
            (pm["start_date"] <= pd.to_datetime(end_date))
            & (
                (pm["mvp_actual_date"].isna())
                | (pm["mvp_actual_date"] >= pd.to_datetime(start_date))
            )
        ]
        delivered = pm.dropna(subset=["mvp_actual_date"])
        delivered = delivered[
            (delivered["mvp_actual_date"] >= pd.to_datetime(start_date))
            & (delivered["mvp_actual_date"] <= pd.to_datetime(end_date))
        ]
        if not delivered.empty:
            delivered["month"] = (
                delivered["mvp_actual_date"].dt.to_period("M").astype("datetime64[ns]")
            )
            delivered["mvp_cycle_days"] = (
                delivered["mvp_actual_date"] - delivered["start_date"]
            ).dt.days
            delivered["on_time"] = (
                delivered["mvp_actual_date"] <= delivered["mvp_target_date"]
            ).astype(int)
            monthly = delivered.groupby("month", as_index=False).agg(
                mvps=("project_name", "count"),
                avg_cycle_days=("mvp_cycle_days", "mean"),
                on_time_rate=("on_time", "mean"),
            )
            st.line_chart(monthly.set_index("month")[["mvps", "avg_cycle_days"]])
            st.dataframe(monthly.sort_values("month"))
        st.metric("Projects Running (now in range)", value=len(running))
        st.dataframe(
            pm[
                [
                    "project_name",
                    "dept",
                    "start_date",
                    "mvp_target_date",
                    "mvp_actual_date",
                ]
            ].sort_values("start_date")
        )
        continue

    # Time Management (weekly)
    if kpi == "time_mgmt":
        tm = metrics.compute_kpi("time_mgmt", df_raw)
        if not tm.empty:
            tm = tm[
                (tm["week_start"] >= pd.to_datetime(start_date))
                & (tm["week_start"] <= pd.to_datetime(end_date))
            ]
            if not tm.empty:
                st.subheader("Weekly Hours (by category)")
                cats = [
                    "development",
                    "debugging_tickets",
                    "mentoring",
                    "devops",
                    "project_management",
                    "meetings",
                ]
                st.bar_chart(tm.set_index("week_start")[cats])

                st.subheader("Weekly Split (%)")
                pct_cols = [c for c in tm.columns if c.endswith("_pct")]
                if pct_cols:
                    st.line_chart(tm.set_index("week_start")[pct_cols])

                st.dataframe(
                    tm[
                        ["week_start", "kw", "total_hours"] + cats + pct_cols
                    ].sort_values("week_start", ascending=False)
                )
            else:
                st.info("No weekly time entries in selected range")
        else:
            st.info("No records")
        continue

    # Default fallback
    df_kpi = metrics.compute_kpi(kpi, df_raw)
    if "month" in df_kpi.columns:
        df_kpi["month"] = pd.to_datetime(df_kpi["month"], errors="coerce")
        st.line_chart(df_kpi.set_index("month"))
    else:
        st.dataframe(df_kpi)

st.markdown("---")

# --- Append new entry UI ---
st.header("➕ Add KPI Entry")

selected_csv_key = st.selectbox("Choose KPI to append to:", list(CSV_SCHEMAS.keys()))

with st.form("append_form"):
    field_inputs = {}

    # derive options for issues.type
    type_options = None
    if selected_csv_key == "issues":
        csv_path = os.path.join(DATA_DIR, f"{selected_csv_key}.csv")
        default_types = ["bug", "PR", "issue", "feature", "task"]
        if os.path.exists(csv_path):
            try:
                existing = pd.read_csv(csv_path)
                if "type" in existing.columns:
                    type_options = sorted(
                        [
                            t
                            for t in existing["type"].dropna().unique().tolist()
                            if isinstance(t, str)
                        ]
                    )
            except Exception:
                type_options = None
        if not type_options:
            type_options = default_types

    # Render inputs
    if selected_csv_key in CSV_SCHEMAS:
        for field in CSV_SCHEMAS[selected_csv_key]:
            # DATE inputs
            if field in (
                "date",
                "date_closed",
                "idea_date",
                "deploy_date",
                "start_date",
                "mvp_target_date",
                "mvp_actual_date",
                "week_start",
            ):
                default = date.today()
                field_inputs[field] = st.date_input(field, value=default)

            # MONTH as date input (we'll save as YYYY-MM)
            elif field == "month":
                field_inputs[field] = st.date_input(field, value=date.today())

            # SELECT boxes
            elif selected_csv_key == "issues" and field == "type":
                field_inputs[field] = st.selectbox(field, type_options)

            elif selected_csv_key == "mentoring" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)
            elif selected_csv_key == "mentoring" and field == "mentoring_type":
                field_inputs[field] = st.selectbox(field, MENTORING_TYPES)

            elif selected_csv_key == "ai_engagement" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)

            elif selected_csv_key == "project_mgmt" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)

            elif selected_csv_key == "apps" and field == "app_type":
                field_inputs[field] = st.selectbox(field, list(APP_TYPES.keys()))

            # TIME MGMT: handle kw as read-only (auto-computed from week_start)
            elif selected_csv_key == "time_mgmt" and field == "kw":
                # Placeholder; will be auto-filled after week_start selected
                field_inputs[field] = st.text_input(
                    field + " (auto)", value="", disabled=True
                )

            # NUMERIC inputs (catch-all for number-like fields)
            elif selected_csv_key == "data_collection" and field in (
                "time_before_sec",
                "time_after_sec",
            ):
                field_inputs[field] = st.number_input(
                    field + " (seconds)", step=1, min_value=0
                )
            elif field in (
                "fields_before",
                "fields_after",
                "time_before_hrs",
                "time_after_hrs",
                "frequency_per_month",
                "active_users",
                "ai_calls",
                "survey_score",
                "learning_hrs",
                "applied_hrs",
                "mentor_hrs",
                "team_time_saved_hrs",
                "implementations",
                "usages",
                "profit_over_legacy_pct",
                "development",
                "debugging_tickets",
                "mentoring",
                "devops",
                "project_management",
                "meetings",
            ):
                # ensure numeric entry for time_mgmt categories
                field_inputs[field] = st.number_input(field, step=1.0, min_value=0.0)
            else:
                field_inputs[field] = st.text_input(field)

    submitted = st.form_submit_button("Append Entry")

    if submitted:
        try:
            # Normalize date formats / computed fields
            for k, v in list(field_inputs.items()):
                if k in (
                    "date",
                    "date_closed",
                    "idea_date",
                    "deploy_date",
                    "start_date",
                    "mvp_target_date",
                    "mvp_actual_date",
                    "week_start",
                ):
                    if hasattr(v, "strftime"):
                        field_inputs[k] = v.strftime("%Y-%m-%d")
                if k == "month":
                    if hasattr(v, "strftime"):
                        field_inputs[k] = v.strftime("%Y-%m")
                if k == "app_type":
                    field_inputs[k] = APP_TYPES.get(v, v)

            # Auto-derive ISO week label (kw) from week_start for time_mgmt
            if selected_csv_key == "time_mgmt":
                ws = field_inputs.get("week_start")
                if ws:
                    y, m, d = [int(x) for x in ws.split("-")]
                    iso = datetime(y, m, d).isocalendar()
                    field_inputs["kw"] = f"{iso.year}-W{iso.week:02d}"
                else:
                    field_inputs["kw"] = ""

            csv_path = os.path.join(DATA_DIR, f"{selected_csv_key}.csv")
            df_new = pd.DataFrame([field_inputs])
            if os.path.exists(csv_path):
                df_existing = pd.read_csv(csv_path)
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new
            df_combined.to_csv(csv_path, index=False)
            st.success(f"✅ Entry appended to {selected_csv_key}.csv")
        except Exception as e:
            st.error(f"❌ Error: {e}")
