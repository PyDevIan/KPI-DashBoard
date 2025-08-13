import pandas as pd
from typing import Callable, Dict

# Registry for KPI functions
KPI_FUNCTIONS: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {}

# Metadata for each KPI (display name, unit, description, source)
KPI_META: Dict[str, Dict] = {
    "apps": {
        "display_name": "Apps – Time Saved & Dev Speed",
        "unit": "hours",
        "description": "Total time saved by apps (hours) and average development speed per app type.",
        "source_csv": "apps.csv",
    },
    "data_collection": {
        "display_name": "Information Gain",
        "unit": "%",
        "description": "Average & weighted information gain (% fields↑) per month.",
        "source_csv": "data_collection.csv",
    },
    "mentoring": {
        "display_name": "Mentoring Impact (by Dept & Type)",
        "unit": "hours",
        "description": "Mentor hours, team hours saved, and ROI (saved / mentor) across departments and mentoring types.",
        "source_csv": "mentoring.csv",
    },
    "project_mgmt": {
        "display_name": "Project Management (MVP Delivery)",
        "unit": "count",
        "description": "Projects running, average MVP cycle (days), and on-time delivery rate.",
        "source_csv": "project_mgmt.csv",
    },
    # Unified KPI
    "worklog": {
        "display_name": "Support Worklog (Tickets & Issues)",
        "unit": "count",
        "description": "Counts and total time for Tickets, Bugs, and Errors; plus daily closures.",
        "source_csv": "worklog.csv",
    },
    "learning": {
        "display_name": "Learning – Efficiency & ROI",
        "unit": "ratio",
        "description": "Efficiency (applied/learning), application rate, time ROI, and average performance delta.",
        "source_csv": "learning.csv",
    },
    "time_mgmt": {
        "display_name": "Time Management (Daily Allocation)",
        "unit": "hours",
        "description": "Daily allocation of hours across Development, Debugging/Tickets, Mentoring, DevOps, Project Management, and Meetings.",
        "source_csv": "time_mgmt.csv",
    },
}


def register_kpi(name: str):
    def decorator(func: Callable[[pd.DataFrame], pd.DataFrame]):
        KPI_FUNCTIONS[name] = func
        return func

    return decorator


# -------------------- APPS (time saved monthly) --------------------
@register_kpi("apps")
def compute_apps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects:
      app_id, app_name, app_type, idea_date, deploy_date, month,
      time_before_hrs, time_after_hrs, frequency_per_month
    Returns: month, total_saved
    """
    df2 = df.copy()
    for c in ("time_before_hrs", "time_after_hrs", "frequency_per_month"):
        df2[c] = pd.to_numeric(df2.get(c), errors="coerce")
    df2["time_saved"] = (df2["time_before_hrs"] - df2["time_after_hrs"]) * df2[
        "frequency_per_month"
    ]
    out = df2.groupby("month", as_index=False).agg(total_saved=("time_saved", "sum"))
    return out


# --------- DATA COLLECTION (Info Gain only) ---------
@register_kpi("data_collection")
def compute_data_collection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects:
      proc_id, proc_name, month, fields_before, fields_after
    Returns per-month:
      avg_info_gain_pct, weighted_info_gain_pct, total_fields_added
    """
    df2 = df.copy()
    for c in ["fields_before", "fields_after"]:
        if c not in df2.columns:
            df2[c] = pd.NA
        df2[c] = pd.to_numeric(df2[c], errors="coerce")

    valid_fields = df2["fields_before"] > 0
    df2.loc[valid_fields, "info_gain_pct"] = (
        df2["fields_after"] / df2["fields_before"] - 1
    ) * 100
    df2["fields_added"] = df2["fields_after"] - df2["fields_before"]

    monthly_totals = df2.groupby("month", as_index=False).agg(
        sum_fields_before=("fields_before", "sum"),
        sum_fields_after=("fields_after", "sum"),
        total_fields_added=("fields_added", "sum"),
    )
    monthly_totals["weighted_info_gain_pct"] = (
        monthly_totals["sum_fields_after"] / monthly_totals["sum_fields_before"] - 1
    ) * 100

    out = (
        df2.groupby("month", as_index=False)
        .agg(
            avg_info_gain_pct=("info_gain_pct", "mean"),
        )
        .merge(
            monthly_totals[["month", "weighted_info_gain_pct", "total_fields_added"]],
            on="month",
            how="left",
        )
    )
    return out


# -------------------- MENTORING --------------------
@register_kpi("mentoring")
def compute_mentoring(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    for c in ["mentor_hrs", "team_time_saved_hrs"]:
        df2[c] = pd.to_numeric(df2[c], errors="coerce")
    df2["month"] = (
        pd.to_datetime(df2["date"], errors="coerce").dt.to_period("M").astype(str)
    )
    df2["roi"] = df2["team_time_saved_hrs"] / df2["mentor_hrs"]
    out = df2.groupby("month", as_index=False).agg(
        mentor_hrs_sum=("mentor_hrs", "sum"),
        team_saved_sum=("team_time_saved_hrs", "sum"),
        avg_roi=("roi", "mean"),
    )
    return out


# -------------------- PROJECT MGMT --------------------
@register_kpi("project_mgmt")
def compute_project_mgmt(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    for c in ["start_date", "mvp_target_date", "mvp_actual_date"]:
        df2[c] = pd.to_datetime(df2[c], errors="coerce")
    df2["mvp_cycle_days"] = (df2["mvp_actual_date"] - df2["start_date"]).dt.days
    df2["on_time"] = (
        (df2["mvp_actual_date"].notna())
        & (df2["mvp_actual_date"] <= df2["mvp_target_date"])
    ).astype(int)
    df2["month"] = df2["mvp_actual_date"].dt.to_period("M").astype("datetime64[ns]")
    return df2


# -------------------- WORKLOG (tickets + issues) --------------------
@register_kpi("worklog")
def compute_worklog(df: pd.DataFrame) -> pd.DataFrame:
    """
    Inputs:
      type (Ticket/Bug/Error), id, date_closed, time_consumed (hours)
    Output:
      one row per day with items_closed and time_consumed_sum (for charts)
    """
    df2 = df.copy()
    df2["date_closed"] = pd.to_datetime(df2["date_closed"], errors="coerce")
    df2["time_consumed"] = pd.to_numeric(
        df2.get("time_consumed"), errors="coerce"
    ).fillna(0.0)
    if "type" in df2.columns:
        mapping = {"ticket": "Ticket", "bug": "Bug", "error": "Error"}
        df2["type"] = (
            df2["type"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map(mapping)
            .fillna(df2["type"])
        )
    df2 = df2.dropna(subset=["date_closed"])
    df2["day"] = df2["date_closed"].dt.floor("D")

    daily = df2.groupby("day", as_index=False).agg(
        items_closed=("id", "count"),
        time_consumed_sum=("time_consumed", "sum"),
    )
    return daily.sort_values("day")


# -------------------- LEARNING --------------------
@register_kpi("learning")
def compute_learning(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    # tolerate missing cols
    for c in [
        "learning_hrs",
        "applied_hrs",
        "applications",
        "delta_performance_pct",
        "time_saved_hrs",
        "cost_eur",
    ]:
        if c not in df2.columns:
            df2[c] = 0
        df2[c] = pd.to_numeric(df2[c], errors="coerce").fillna(0)

    df2["date"] = pd.to_datetime(df2.get("date"), errors="coerce")
    df2["month"] = df2["date"].dt.to_period("M").astype(str)

    # core metrics
    df2["efficiency"] = (
        (df2["applied_hrs"] / df2["learning_hrs"]).replace([float("inf")], 0).fillna(0)
    )
    df2["roi_time"] = (
        (df2["time_saved_hrs"] / df2["learning_hrs"])
        .replace([float("inf")], 0)
        .fillna(0)
    )
    df2["delta_pct"] = pd.to_numeric(
        df2["delta_performance_pct"], errors="coerce"
    ).fillna(0)

    # monthly aggregates
    out = df2.groupby("month", as_index=False).agg(
        learning_hrs_sum=("learning_hrs", "sum"),
        applied_hrs_sum=("applied_hrs", "sum"),
        applications_sum=("applications", "sum"),
        time_saved_sum=("time_saved_hrs", "sum"),
        avg_efficiency=("efficiency", "mean"),
        avg_roi_time=("roi_time", "mean"),
        avg_delta_pct=("delta_pct", "mean"),
    )
    # derive application rate (apps per week in the month)
    # (approx weeks = days_in_month/7)
    month_start = pd.to_datetime(out["month"])
    next_month = (month_start.dt.to_period("M") + 1).astype("datetime64[ns]")
    days = (next_month - month_start).dt.days.clip(lower=1)
    out["application_rate_pw"] = out["applications_sum"] / (days / 7.0)
    return out


# -------------------- TIME MGMT (DAILY) --------------------
@register_kpi("time_mgmt")
def compute_time_mgmt(df: pd.DataFrame) -> pd.DataFrame:
    """
    Inputs (daily):
      date, development, debugging_tickets, mentoring, devops, project_management, meetings
    Output: one row per day with totals and % split.
    """
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")

    cats = [
        "development",
        "debugging_tickets",
        "mentoring",
        "devops",
        "project_management",
        "meetings",
    ]
    for c in cats:
        df2[c] = pd.to_numeric(df2.get(c), errors="coerce").fillna(0)

    df2["total_hours"] = df2[cats].sum(axis=1)
    for c in cats:
        df2[f"{c}_pct"] = (df2[c] / df2["total_hours"] * 100).where(
            df2["total_hours"] > 0, 0
        )

    out_cols = ["date", "total_hours"] + cats + [f"{c}_pct" for c in cats]
    return df2[out_cols].sort_values("date")


# -------------------- helpers --------------------
def load_kpi(csv_path: str, parse_dates=None) -> pd.DataFrame:
    suggested = [
        "month",
        "date",
        "date_closed",
        "idea_date",
        "deploy_date",
        "start_date",
        "mvp_target_date",
        "mvp_actual_date",
    ]
    df_preview = pd.read_csv(csv_path, nrows=1)
    cols_to_parse = [col for col in suggested if col in df_preview.columns]
    return pd.read_csv(csv_path, parse_dates=cols_to_parse)


def compute_kpi(name: str, df: pd.DataFrame) -> pd.DataFrame:
    if name not in KPI_FUNCTIONS:
        raise KeyError(f"Unknown KPI '{name}'. Available: {list(KPI_FUNCTIONS.keys())}")
    return KPI_FUNCTIONS[name](df)


def list_kpis() -> list:
    return list(KPI_FUNCTIONS.keys())


def get_kpi_meta(name: str) -> dict:
    return KPI_META.get(name, {})
