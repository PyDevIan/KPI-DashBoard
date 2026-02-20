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
    # Learning (core skills)
    "learning": [
        "date",
        "core_skill",
        "skills_tech_tags",
        "time_spent_hrs",
        "notes",
    ],
    # Time management (daily)
    "time_mgmt": [
        "date",
        "development",
        "debugging_tickets",
        "learning",
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
WORKLOG_TYPES = ["Ticket", "Bug", "Error"]
CORE_SKILL_OPTIONS = [
    "AI/ML engineering",
    "Backend development",
    "Frontend development",
    "Data/MLOps",
    "Deploy/Cloud",
    "Lifecycle",
    "Project Management",
]

# KPIs that always show as top flag cards (order matters)
CRITICAL_KPIS = [
    "worklog",
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
@st.cache_data(ttl=60)
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

    if kpi == "learning":
        # headline = invested hours over the selected range
        lr = metrics.compute_kpi("learning", df_raw)
        if not lr.empty:
            lr["month"] = pd.to_datetime(lr["month"], errors="coerce")
            lr = lr[
                (lr["month"] >= pd.to_datetime(start_date))
                & (lr["month"] <= pd.to_datetime(end_date))
            ]
            invested = (
                float(lr["time_spent_sum"].sum()) if "time_spent_sum" in lr else 0.0
            )
            col.metric("Hours Invested", f"{invested:.1f} hrs")
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
        learning_raw = df_raw.copy()
        learning_raw["date"] = pd.to_datetime(learning_raw.get("date"), errors="coerce")
        learning_raw["time_spent_hrs"] = pd.to_numeric(
            learning_raw.get("time_spent_hrs", learning_raw.get("learning_hrs", 0)),
            errors="coerce",
        ).fillna(0.0)
        if "core_skill" not in learning_raw.columns:
            learning_raw["core_skill"] = "Uncategorized"
        learning_raw["core_skill"] = learning_raw["core_skill"].fillna("Uncategorized")

        learning_filtered = learning_raw.dropna(subset=["date"])
        learning_filtered = learning_filtered[
            (learning_filtered["date"] >= pd.to_datetime(start_date))
            & (learning_filtered["date"] <= pd.to_datetime(end_date))
        ].copy()

        if learning_filtered.empty:
            st.info("No records")
            continue

        daily_learning = (
            learning_filtered.assign(day=learning_filtered["date"].dt.floor("D"))
            .groupby("day", as_index=False)
            .agg(time_spent_sum=("time_spent_hrs", "sum"))
            .sort_values("day")
        )

        daily_chart = (
            alt.Chart(daily_learning)
            .mark_bar()
            .encode(
                x=alt.X("day:T", title="Day"),
                y=alt.Y("time_spent_sum:Q", title="Hours Invested"),
                tooltip=["day:T", "time_spent_sum:Q"],
            )
            .properties(height=260)
        )
        st.subheader("Learning Hours by Day")
        st.altair_chart(daily_chart, use_container_width=True)

        by_skill_total = (
            learning_filtered.groupby("core_skill", as_index=False)
            .agg(total_hours=("time_spent_hrs", "sum"))
            .sort_values("total_hours", ascending=False)
        )
        core_skill_chart = (
            alt.Chart(by_skill_total)
            .mark_bar()
            .encode(
                x=alt.X("core_skill:N", title="Core Skill", sort="-y"),
                y=alt.Y("total_hours:Q", title="Hours Invested"),
                color=alt.Color("core_skill:N", title="Core Skill"),
                tooltip=["core_skill:N", "total_hours:Q"],
            )
            .properties(height=300)
        )
        st.subheader("Hours Invested by Core Skill")
        st.altair_chart(core_skill_chart, use_container_width=True)

        skills_for_summary = learning_raw.dropna(subset=["date"]).copy()
        if "skills_tech_tags" not in skills_for_summary.columns:
            skills_for_summary["skills_tech_tags"] = ""
        skills_for_summary["skills_tech_tags"] = skills_for_summary["skills_tech_tags"].fillna("")
        core_skill_summary = (
            skills_for_summary.groupby("core_skill", as_index=False)
            .agg(
                technologies_acquired=(
                    "skills_tech_tags",
                    lambda x: [
                        t
                        for t in sorted(
                            {
                                tag.strip()
                                for row in x.astype(str)
                                for tag in row.split(",")
                                if tag.strip()
                            }
                        )
                    ],
                )
            )
            .sort_values("core_skill")
        )

        st.subheader("Core Skills Summary")
        st.dataframe(core_skill_summary)

        st.dataframe(
            daily_learning.rename(
                columns={
                    "day": "Date",
                    "time_spent_sum": "Time Spent (hrs)",
                }
            )
        )
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
            "learning",
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
            elif selected_csv_key in ["time_mgmt", "worklog"] and field in [
                "development",
                "debugging_tickets",
                "learning",
                "devops",
                "project_management",
                "meetings",
                "time_consumed",
            ]:
                c1, c2 = st.columns(2)
                hrs = c1.number_input(f"{field} (hours)", step=1, min_value=0, value=0)
                mins = c2.number_input(
                    f"{field} (minutes)", step=5, min_value=0, max_value=59, value=0
                )
                field_inputs[field] = hrs + mins / 60.0
            elif field == "month":
                field_inputs[field] = st.date_input(field, value=date.today())

            # Selects
            elif selected_csv_key == "project_mgmt" and field == "dept":
                field_inputs[field] = st.selectbox(field, DEPT_OPTIONS)
            elif selected_csv_key == "worklog" and field == "type":
                field_inputs[field] = st.selectbox(field, WORKLOG_TYPES)
            elif selected_csv_key == "learning" and field == "core_skill":
                field_inputs[field] = st.selectbox(field, CORE_SKILL_OPTIONS)

            # Numerics
            elif field in (
                "time_spent_hrs",
                "development",
                "debugging_tickets",
                "learning",
                "devops",
                "project_management",
                "meetings",
                "time_consumed",
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
