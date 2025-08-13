import streamlit as st
import pandas as pd
import glob, os
from datetime import date
import altair as alt
import metrics

st.set_page_config(page_title="Career KPI Dashboard", layout="wide")
DATA_DIR = "data"

# --- CSV Schema Map (for data-entry form) ---
CSV_SCHEMAS = {
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
    "data_collection": [
        "proc_id",
        "proc_name",
        "month",
        "fields_before",
        "fields_after",  # Speed cols removed
    ],
    "mentoring": [
        "session_id",
        "date",
        "dept",
        "mentoring_type",
        "mentor_hrs",
        "team_time_saved_hrs",
    ],
    "project_mgmt": [
        "project_name",
        "dept",
        "start_date",
        "mvp_target_date",
        "mvp_actual_date",
    ],
    # Unified Tickets + Issues
    "worklog": [
        "type",  # Ticket/Bug/Error
        "id",
        "date_closed",
        "time_consumed",  # hours (float)
    ],
    # Learning & Efficiency
    "learning": [
        "date",
        "skill",  # NEW (optional)
        "learning_hrs",
        "applied_hrs",
        "applications",  # NEW
        "delta_performance_pct",  # NEW
        "time_saved_hrs",  # NEW
        "cost_eur",  # NEW (optional)
    ],
    # Time management (daily)
    "time_mgmt": [
        "date",
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
    "QA",
    "QC",
    "QColives",
    "RND",
    "BIO",
]
MENTORING_TYPES = ["prompt_eng", "nocode_guidance", "ai_assistant_util"]
APP_TYPES = {
    "Simple Data Collection/Procedure": "simple",
    "AI Full App": "ai_full",
    "AI Assistant App": "ai_assistant",
}
WORKLOG_TYPES = ["Ticket", "Bug", "Error"]

# KPIs that always show as top flag cards (order matters)
CRITICAL_KPIS = [
    "apps",
    "worklog",
    "data_collection",
    "mentoring",
    "project_mgmt",
    "time_mgmt",
    "learning",
]

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


# --- Helpers & cache ---
@st.cache_data(show_spinner=False)
def cached_load(path: str) -> pd.DataFrame:
    return metrics.load_kpi(path)


def zero_fill_days(df: pd.DataFrame, date_col: str, start, end) -> pd.DataFrame:
    rng = pd.date_range(pd.to_datetime(start), pd.to_datetime(end), freq="D")
    return (
        df.set_index(date_col)
        .reindex(rng)
        .fillna(0)
        .rename_axis(date_col)
        .reset_index()
    )


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

# If nothing selected, show reference
if not selected_kpis:
    st.title("🏆 Personal Career KPI Dashboard")
    st.subheader("📊 KPI Reference Table")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "KPI Name": meta.get("display_name", key),
                    "What It Measures": meta.get("description", ""),
                    "Value / Unit": meta.get("unit", ""),
                    "Data Source (CSV)": meta.get("source_csv", ""),
                    "Pinned (Flag KPI)": "✅" if key in CRITICAL_KPIS else "",
                }
                for key, meta in metrics.KPI_META.items()
                if key in metrics.list_kpis()
            ]
        )
    )
    st.stop()

st.title("🏆 Personal Career KPI Dashboard")

# =========================
# FLAG KPIs (cards only)
# =========================
flag_kpis = [k for k in CRITICAL_KPIS if k in selected_kpis]
detail_kpis = selected_kpis  # always show plots/details for every selected KPI


cols = st.columns(len(flag_kpis)) if flag_kpis else [st]
for idx, kpi in enumerate(flag_kpis):
    col = cols[idx]
    df_raw = cached_load(uploads[kpi])
    df_kpi = metrics.compute_kpi(kpi, df_raw)

    meta = metrics.get_kpi_meta(kpi)
    label = meta.get("display_name", kpi.replace("_", " ").title())
    unit = meta.get("unit", "")
    help_ = meta.get("description", "")

    # Range filter for monthly outputs
    if "month" in df_kpi.columns:
        df_kpi["month"] = pd.to_datetime(df_kpi["month"], errors="coerce")
        df_kpi = df_kpi[
            (df_kpi["month"] >= pd.to_datetime(start_date))
            & (df_kpi["month"] <= pd.to_datetime(end_date))
        ]

    # ---- WORKLOG: show ONLY the 2 headline KPIs here
    if kpi == "worklog":
        w = df_raw.copy()
        w["date_closed"] = pd.to_datetime(w["date_closed"], errors="coerce")
        w = w.dropna(subset=["date_closed"])
        w = w[
            (w["date_closed"] >= pd.to_datetime(start_date))
            & (w["date_closed"] <= pd.to_datetime(end_date))
        ]
        mapping = {"ticket": "Ticket", "bug": "Bug", "error": "Error"}
        w["type"] = (
            w["type"].astype(str).str.strip().str.lower().map(mapping).fillna(w["type"])
        )
        w["time_consumed"] = pd.to_numeric(
            w.get("time_consumed"), errors="coerce"
        ).fillna(0.0)

        total_count = int(len(w))
        total_time = float(w["time_consumed"].sum())

        col.metric(
            label=f"{label} – Total Closed", value=f"{total_count} {unit}", help=help_
        )
        col.metric(label="Total Time Consumed", value=f"{total_time:.1f} hours")
        continue

    # ---- DATA COLLECTION (Info Gain only): headline = weighted info gain avg
    if kpi == "data_collection" and not df_kpi.empty:
        value = df_kpi["weighted_info_gain_pct"].mean(skipna=True)
        col.metric(
            label=f"{label} (Weighted Avg)",
            value=f"{value:.2f} %",
            help="Weighted by fields_before; higher is better",
        )
        continue
    if kpi == "learning":
        # headline = efficiency & time ROI over the selected range
        lr = metrics.compute_kpi("learning", df_raw)
        if not lr.empty:
            lr["month"] = pd.to_datetime(lr["month"], errors="coerce")
            lr = lr[
                (lr["month"] >= pd.to_datetime(start_date))
                & (lr["month"] <= pd.to_datetime(end_date))
            ]
            eff = float(lr["avg_efficiency"].mean()) if "avg_efficiency" in lr else 0.0
            roi = float(lr["avg_roi_time"].mean()) if "avg_roi_time" in lr else 0.0
            col.metric(
                "Learning Efficiency",
                f"{eff:.2f} ratio",
                help="applied_hrs / learning_hrs",
            )
            col.metric("Time ROI", f"{roi:.2f}x", help="time_saved_hrs / learning_hrs")
        else:
            col.info("No records")
        continue

    # ---- APPS: headline = total saved; plus avg dev speed
    if kpi == "apps":
        total_hours_saved = (
            float(df_kpi["total_saved"].sum())
            if ("total_saved" in df_kpi.columns)
            else 0.0
        )
        col.metric(
            label=f"{label} – Total Saved",
            value=f"{total_hours_saved:.1f} hours",
            help="Sum of (time_before - time_after) * frequency across apps in range",
        )

        if set(["deploy_date", "idea_date"]).issubset(df_raw.columns):
            sp = df_raw.copy()
            sp["deploy_date"] = pd.to_datetime(sp["deploy_date"], errors="coerce")
            sp["idea_date"] = pd.to_datetime(sp["idea_date"], errors="coerce")
            sp = sp.dropna(subset=["deploy_date", "idea_date"])
            sp = sp[
                (sp["deploy_date"] >= pd.to_datetime(start_date))
                & (sp["deploy_date"] <= pd.to_datetime(end_date))
            ]
            if not sp.empty:
                sp["dev_days"] = (sp["deploy_date"] - sp["idea_date"]).dt.days
                col.metric(
                    label="Avg Dev Speed (All Types)",
                    value=f"{float(sp['dev_days'].mean()):.1f} days",
                )
        continue

    # ---- MENTORING: headline = ROI
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

    # ---- PROJECT MGMT: headline = projects running (only here; not in details)
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
        col.metric(label="Projects Running", value=f"{len(running)}", help=help_)
        continue

    # ---- TIME MGMT: headline = weighted Dev Focus %
    if kpi == "time_mgmt":
        tm = metrics.compute_kpi("time_mgmt", df_raw)
        if tm.empty:
            col.info("No records")
            continue
        tm = tm[
            (tm["date"] >= pd.to_datetime(start_date))
            & (tm["date"] <= pd.to_datetime(end_date))
        ]
        if tm.empty:
            col.info("No records")
            continue
        dev_sum = float(pd.to_numeric(tm["development"], errors="coerce").sum())
        total_sum = float(pd.to_numeric(tm["total_hours"], errors="coerce").sum())
        dev_focus = (dev_sum / total_sum * 100) if total_sum > 0 else 0.0
        col.metric(
            label="Time Management (Dev Focus)",
            value=f"{dev_focus:.1f} %",
            help="Weighted Dev Focus across selected days (ΣDevelopment / ΣTotal Hours)",
        )
        continue

    # ---- Fallback
    if df_kpi.empty:
        col.info("No records")
        continue
    metric_cols = [c for c in df_kpi.columns if c != "month"]
    if not metric_cols:
        col.info("No metric columns")
        continue
    value = (
        df_kpi.sort_values("month").iloc[-1][metric_cols[0]]
        if "month" in df_kpi.columns
        else df_kpi[metric_cols[0]].iloc[-1]
    )
    fmt = "{:.0f}" if unit in ("count",) else "{:.2f}"
    col.metric(label=label, value=f"{fmt.format(value)} {unit}", help=help_)

st.header("Trends & Details")

# =========================
# DETAILS (no duplicate KPIs here)
# =========================
for kpi in detail_kpis:
    df_raw = cached_load(uploads[kpi])
    meta = metrics.get_kpi_meta(kpi)
    st.subheader(meta.get("display_name", kpi.replace("_", " ").title()))
    st.caption(meta.get("description", ""))

    # ---- WORKLOG details: side-by-side numbers, then daily plot
    if kpi == "worklog":
        w = df_raw.copy()
        w["date_closed"] = pd.to_datetime(w["date_closed"], errors="coerce")
        w = w.dropna(subset=["date_closed"])
        w = w[
            (w["date_closed"] >= pd.to_datetime(start_date))
            & (w["date_closed"] <= pd.to_datetime(end_date))
        ]
        mapping = {"ticket": "Ticket", "bug": "Bug", "error": "Error"}
        w["type"] = (
            w["type"].astype(str).str.strip().str.lower().map(mapping).fillna(w["type"])
        )
        w["time_consumed"] = pd.to_numeric(
            w.get("time_consumed"), errors="coerce"
        ).fillna(0.0)

        # side-by-side counts
        counts = w["type"].value_counts().to_dict()
        bugs = int(counts.get("Bug", 0))
        errors = int(counts.get("Error", 0))
        tickets = int(counts.get("Ticket", 0))

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Bugs = {bugs}**")
        with c2:
            st.markdown(f"**Errors = {errors}**")
        with c3:
            st.markdown(f"**Tickets = {tickets}**")

        # daily total closed: bars + 7-day moving average line (multicolor) with zero-fill
        daily = w.copy()
        daily["day"] = daily["date_closed"].dt.floor("D")
        daily_counts = (
            daily.groupby("day", as_index=False)
            .size()
            .rename(columns={"size": "closed"})
        ).sort_values("day")
        daily_counts = zero_fill_days(daily_counts, "day", start_date, end_date)
        daily_counts["closed"] = daily_counts["closed"].astype(int)
        daily_counts["closed_ma7"] = (
            daily_counts["closed"].rolling(7, min_periods=1).mean()
        )

        st.subheader("Closed per Day")
        bars = (
            alt.Chart(daily_counts)
            .mark_bar()
            .encode(
                x=alt.X("day:T", title="Day"),
                y=alt.Y("closed:Q", title="Closed (count)"),
                tooltip=["day:T", "closed:Q"],
            )
        )
        line = (
            alt.Chart(daily_counts)
            .mark_line(point=True)
            .encode(
                x="day:T",
                y=alt.Y("closed_ma7:Q", title="7-day avg"),
                tooltip=["day:T", "closed_ma7:Q"],
            )
        )
        st.altair_chart((bars + line).properties(height=260), use_container_width=True)

        # latest details (optional)
        st.dataframe(
            w[["type", "id", "date_closed", "time_consumed"]]
            .sort_values("date_closed", ascending=False)
            .head(100)
        )
        continue

    if kpi == "learning":
        lr = metrics.compute_kpi("learning", df_raw)
        if lr.empty:
            st.info("No records")
            continue
        lr["month"] = pd.to_datetime(lr["month"], errors="coerce")
        lr = lr[
            (lr["month"] >= pd.to_datetime(start_date))
            & (lr["month"] <= pd.to_datetime(end_date))
        ].sort_values("month")

        # Multicolor lines: Efficiency & Time ROI
        line = (
            alt.Chart(lr)
            .transform_fold(["avg_efficiency", "avg_roi_time"], as_=["metric", "value"])
            .mark_line(point=True)
            .encode(
                x=alt.X("month:T", title="Month"),
                y=alt.Y("value:Q", title="Ratio"),
                color=alt.Color(
                    "metric:N", title="Metric", sort=["avg_efficiency", "avg_roi_time"]
                ),
                tooltip=["month:T", "metric:N", "value:Q"],
            )
            .properties(height=260)
        )
        st.subheader("Learning Efficiency & Time ROI")
        st.altair_chart(line, use_container_width=True)

        # Bars: Applications and Time Saved
        bars = (
            alt.Chart(lr)
            .transform_fold(
                ["applications_sum", "time_saved_sum"], as_=["metric", "value"]
            )
            .mark_bar()
            .encode(
                x=alt.X("month:T", title="Month"),
                y=alt.Y("value:Q", title="Count / Hours"),
                color=alt.Color(
                    "metric:N", title="", sort=["applications_sum", "time_saved_sum"]
                ),
                tooltip=["month:T", "metric:N", "value:Q"],
            )
            .properties(height=260)
        )
        st.subheader("Applications & Time Saved")
        st.altair_chart(bars, use_container_width=True)

        st.dataframe(
            lr[
                [
                    "month",
                    "learning_hrs_sum",
                    "applied_hrs_sum",
                    "applications_sum",
                    "time_saved_sum",
                    "avg_efficiency",
                    "avg_roi_time",
                    "avg_delta_pct",
                    "application_rate_pw",
                ]
            ].rename(
                columns={
                    "learning_hrs_sum": "Learning (hrs)",
                    "applied_hrs_sum": "Applied (hrs)",
                    "applications_sum": "Applications",
                    "time_saved_sum": "Time Saved (hrs)",
                    "avg_efficiency": "Efficiency",
                    "avg_roi_time": "Time ROI",
                    "avg_delta_pct": "Δ Performance (%)",
                    "application_rate_pw": "Apps / week",
                }
            )
        )
        continue

    # ---- Data Collection (Info Gain only): weighted vs average (two-color line)
    if kpi == "data_collection":
        d = metrics.compute_kpi(kpi, df_raw)
        if not d.empty:
            d["month"] = pd.to_datetime(d["month"], errors="coerce")
            d = d[
                (d["month"] >= pd.to_datetime(start_date))
                & (d["month"] <= pd.to_datetime(end_date))
            ][["month", "avg_info_gain_pct", "weighted_info_gain_pct"]].sort_values(
                "month"
            )
            d_long = d.melt("month", var_name="series", value_name="value")
            chart = (
                alt.Chart(d_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:T", title="Month"),
                    y=alt.Y("value:Q", title="Info Gain (%)"),
                    color=alt.Color(
                        "series:N",
                        title="Series",
                        sort=["weighted_info_gain_pct", "avg_info_gain_pct"],
                        legend=alt.Legend(orient="top"),
                    ),
                    tooltip=["month:T", "series:N", "value:Q"],
                )
                .properties(height=260)
            )
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(
                d.rename(
                    columns={
                        "avg_info_gain_pct": "Avg Info Gain (%)",
                        "weighted_info_gain_pct": "Weighted Info Gain (%)",
                    }
                )
            )
        else:
            st.info("No records")
        continue

    # ---- Apps: monthly saved + 3-month rolling avg
    if kpi == "apps":
        df_apps = metrics.compute_kpi("apps", df_raw)
        if not df_apps.empty:
            df_apps["month"] = pd.to_datetime(df_apps["month"], errors="coerce")
            df_apps = df_apps[
                (df_apps["month"] >= pd.to_datetime(start_date))
                & (df_apps["month"] <= pd.to_datetime(end_date))
            ].sort_values("month")
            df_apps["saved_ma3"] = (
                df_apps["total_saved"].rolling(3, min_periods=1).mean()
            )

            line1 = (
                alt.Chart(df_apps)
                .mark_line(point=True)
                .encode(
                    x=alt.X("month:T", title="Month"),
                    y=alt.Y("total_saved:Q", title="Hours Saved"),
                    tooltip=["month:T", "total_saved:Q"],
                )
            )
            line2 = (
                alt.Chart(df_apps)
                .mark_line(strokeDash=[4, 4])
                .encode(
                    x="month:T", y="saved_ma3:Q", tooltip=["month:T", "saved_ma3:Q"]
                )
            )
            st.subheader("Hours Saved (Monthly & 3-mo avg)")
            st.altair_chart(
                (line1 + line2).properties(height=260), use_container_width=True
            )
        else:
            st.info("No records")

        # per-type dev speed (extra insight)
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
        continue

    # ---- Mentoring: department/type breakdowns
    if kpi == "mentoring":
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
            st.subheader("Per-Department Mentoring")
            if not per_dept.empty:
                st.bar_chart(per_dept.set_index("dept")[["mentor_hrs", "team_saved"]])
                st.dataframe(per_dept.sort_values("team_saved", ascending=False))

            per_type = m.groupby("mentoring_type", as_index=False).agg(
                mentor_hrs=("mentor_hrs", "sum"),
                team_saved=("team_time_saved_hrs", "sum"),
            )
            st.subheader("Per-Type Mentoring")
            st.dataframe(per_type.sort_values("team_saved", ascending=False))
        else:
            st.info("No mentoring sessions in selected range")
        continue

    # ---- Project Mgmt: MVPs bars + cycle-days line
    if kpi == "project_mgmt":
        pm = df_raw.copy()
        for c in ["start_date", "mvp_target_date", "mvp_actual_date"]:
            pm[c] = pd.to_datetime(pm[c], errors="coerce")
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
            monthly = (
                delivered.groupby("month", as_index=False)
                .agg(
                    mvps=("project_name", "count"),
                    avg_cycle_days=("mvp_cycle_days", "mean"),
                    on_time_rate=("on_time", "mean"),
                )
                .sort_values("month")
            )

            bars = (
                alt.Chart(monthly)
                .mark_bar()
                .encode(
                    x=alt.X("month:T", title="Month"),
                    y=alt.Y("mvps:Q", title="MVPs Delivered"),
                    tooltip=["month:T", "mvps:Q"],
                )
            )
            line = (
                alt.Chart(monthly)
                .mark_line(point=True)
                .encode(
                    x="month:T",
                    y=alt.Y("avg_cycle_days:Q", title="Avg Cycle (days)"),
                    tooltip=["month:T", "avg_cycle_days:Q"],
                )
            )
            st.subheader("MVPs & Avg Cycle")
            st.altair_chart(
                (bars + line).properties(height=260), use_container_width=True
            )
            st.dataframe(monthly)
        else:
            st.info("No MVP deliveries in selected range")
        continue

    # ---- Time Mgmt: stacked bars + pie
    if kpi == "time_mgmt":
        tm = metrics.compute_kpi("time_mgmt", df_raw)
        if tm.empty:
            st.info("No records")
            continue
        tm = tm[
            (tm["date"] >= pd.to_datetime(start_date))
            & (tm["date"] <= pd.to_datetime(end_date))
        ]
        if tm.empty:
            st.info("No daily time entries in selected range")
            continue

        tm = tm.sort_values("date").copy()
        tm["day"] = tm["date"].dt.strftime("%Y-%m-%d")
        day_order = tm["day"].tolist()

        cats = [
            "development",
            "debugging_tickets",
            "mentoring",
            "devops",
            "project_management",
            "meetings",
        ]
        hours_long = tm.melt(
            id_vars=["day"], value_vars=cats, var_name="category", value_name="hours"
        )

        chart_hours = (
            alt.Chart(hours_long)
            .mark_bar()
            .encode(
                x=alt.X("day:N", sort=day_order, title="Day"),
                y=alt.Y("hours:Q", stack="zero", title="Hours"),
                color="category:N",
                tooltip=["day", "category", "hours"],
            )
            .properties(height=260)
        )
        st.subheader("Daily Hours (by category)")
        st.altair_chart(chart_hours, use_container_width=True)

        totals = hours_long.groupby("category", as_index=False)["hours"].sum()
        pie = (
            alt.Chart(totals)
            .mark_arc(outerRadius=110)
            .encode(
                theta=alt.Theta("hours:Q"),
                color=alt.Color("category:N"),
                tooltip=["category", "hours"],
            )
            .properties(height=280)
        )
        st.subheader("Time Allocation (selected range)")
        st.altair_chart(pie, use_container_width=True)

        st.dataframe(
            tm[
                ["date", "day", "total_hours"]
                + cats
                + [c for c in tm.columns if c.endswith("_pct")]
            ].sort_values("date", ascending=False)
        )
        continue

    # ---- Default: just show the DataFrame
    st.dataframe(metrics.compute_kpi(kpi, df_raw))

st.markdown("---")

# --- Append new entry UI ---
st.header("➕ Add KPI Entry")
selected_csv_key = st.selectbox("Choose KPI to append to:", list(CSV_SCHEMAS.keys()))

with st.form("append_form"):
    field_inputs = {}
    if selected_csv_key in CSV_SCHEMAS:
        for field in CSV_SCHEMAS[selected_csv_key]:
            # Dates
            if field in (
                "date",
                "date_closed",
                "idea_date",
                "deploy_date",
                "start_date",
                "mvp_target_date",
                "mvp_actual_date",
            ):
                field_inputs[field] = st.date_input(field, value=date.today())
            elif field == "month":
                field_inputs[field] = st.date_input(field, value=date.today())

            # Selects
            elif selected_csv_key == "mentoring" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)
            elif selected_csv_key == "mentoring" and field == "mentoring_type":
                field_inputs[field] = st.selectbox(field, MENTORING_TYPES)
            elif selected_csv_key == "project_mgmt" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)
            elif selected_csv_key == "apps" and field == "app_type":
                field_inputs[field] = st.selectbox(field, list(APP_TYPES.keys()))
            elif selected_csv_key == "worklog" and field == "type":
                field_inputs[field] = st.selectbox(field, WORKLOG_TYPES)
    

            # Numerics
            elif field in (
                "fields_before",
                "fields_after",
                "time_before_hrs",
                "time_after_hrs",
                "frequency_per_month",
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
                "time_consumed",
                "applications",
                "delta_performance_pct",
                "time_saved_hrs",
                "cost_eur",
            ):
                field_inputs[field] = st.number_input(field, step=1.0, min_value=0.0)
            else:
                field_inputs[field] = st.text_input(field)

    submitted = st.form_submit_button("Append Entry")
    if submitted:
        try:
            for k, v in list(field_inputs.items()):
                if k in (
                    "date",
                    "date_closed",
                    "idea_date",
                    "deploy_date",
                    "start_date",
                    "mvp_target_date",
                    "mvp_actual_date",
                ):
                    if hasattr(v, "strftime"):
                        field_inputs[k] = v.strftime("%Y-%m-%d")
                if k == "month" and hasattr(v, "strftime"):
                    field_inputs[k] = v.strftime("%Y-%m")
                if k == "app_type":
                    field_inputs[k] = APP_TYPES.get(v, v)

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
