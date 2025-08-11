# metrics.py
import pandas as pd
from typing import Callable, Dict

# Registry for KPI functions
KPI_FUNCTIONS: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {}

# Metadata for each KPI (display name, unit, description)
KPI_META: Dict[str, Dict] = {
    "apps": {
        "display_name": "Apps – Time Saved & Dev Speed",
        "unit": "hours",
        "description": "Total time saved by apps (hours) and average development speed per app type.",
        "source_csv": "apps.csv",
    },
    "data_collection": {
        "display_name": "Information Gain & Speed",
        "unit": "%",
        "description": "Weighted info gain (% fields↑) and speed improvement (% time↓). Time stored in seconds; the UI shows deltas in hours.",
        "source_csv": "data_collection.csv",
    },
    "mentoring": {
        "display_name": "Mentoring Impact (by Dept & Type)",
        "unit": "hours",
        "description": "Mentor hours, team hours saved, and ROI (saved / mentor) across departments and mentoring types.",
        "source_csv": "mentoring.csv",
    },
    "ai_engagement": {
        "display_name": "AI Engagement (Dept Usage)",
        "unit": "events",
        "description": "Active users, AI calls, and survey score by department.",
        "source_csv": "ai_engagement.csv",
    },
    "project_mgmt": {
        "display_name": "Project Management (MVP Delivery)",
        "unit": "count",
        "description": "Projects running, average MVP cycle (days), and on-time delivery rate.",
        "source_csv": "project_mgmt.csv",
    },
    "tickets": {
        "display_name": "Tickets Resolved",
        "unit": "count",
        "description": "Total number of resolved tickets in selected date range.",
        "source_csv": "tickets.csv",
    },
    "issues": {
        "display_name": "Issues & Bugs Resolved",
        "unit": "count",
        "description": "Total issues in range and per-type breakdown.",
        "source_csv": "issues.csv",
    },
    "learning": {
        "display_name": "Learning – Efficiency & Profit",
        "unit": "ratio",
        "description": "Applied/learning efficiency and average profit over legacy (%).",
        "source_csv": "learning.csv",
    },
    "time_mgmt": {
        "display_name": "Time Management (Weekly Allocation)",
        "unit": "hours",
        "description": "Weekly allocation of hours across Development, Debugging/Tickets, Mentoring, DevOps, Project Management, and Meetings. Cards show average Development% over the selected range.",
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
    Expects columns:
      app_id, app_name, app_type, idea_date, deploy_date, month,
      time_before_hrs, time_after_hrs, frequency_per_month
    Returns monthly totals: month, total_saved
    """
    df2 = df.copy()
    for c in ("time_before_hrs", "time_after_hrs", "frequency_per_month"):
        df2[c] = pd.to_numeric(df2.get(c), errors="coerce")
    df2["time_saved"] = (df2["time_before_hrs"] - df2["time_after_hrs"]) * df2[
        "frequency_per_month"
    ]
    out = df2.groupby("month", as_index=False).agg(total_saved=("time_saved", "sum"))
    return out


# --------- DATA COLLECTION (info gain % + speed %; seconds in CSV) ---------
@register_kpi("data_collection")
def compute_info_speed(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expected columns:
      proc_id, proc_name, month, fields_before, fields_after, time_before_sec, time_after_sec
    Returns per-month:
      avg_info_gain_pct, weighted_info_gain_pct, avg_speed_impr_pct, avg_speed_delta_sec, total_fields_added
    """
    df2 = df.copy()
    # Numeric sanitation
    for c in ["fields_before", "fields_after", "time_before_sec", "time_after_sec"]:
        if c not in df2.columns:
            df2[c] = pd.NA
        df2[c] = pd.to_numeric(df2[c], errors="coerce")

    # Info gain (%)
    valid_fields = df2["fields_before"] > 0
    df2.loc[valid_fields, "info_gain_pct"] = (
        df2["fields_after"] / df2["fields_before"] - 1
    ) * 100
    df2["fields_added"] = df2["fields_after"] - df2["fields_before"]

    # Speed improvement (%) and delta (sec)
    valid_time = df2["time_before_sec"] > 0
    df2.loc[valid_time, "speed_impr_pct"] = (
        (df2["time_before_sec"] - df2["time_after_sec"]) / df2["time_before_sec"] * 100
    )
    df2["speed_delta_sec"] = (
        df2["time_after_sec"] - df2["time_before_sec"]
    )  # negative == faster

    # Weighted info gain (%), by fields_before
    monthly_totals = df2.groupby("month", as_index=False).agg(
        sum_fields_before=("fields_before", "sum"),
        sum_fields_after=("fields_after", "sum"),
    )
    monthly_totals["weighted_info_gain_pct"] = (
        monthly_totals["sum_fields_after"] / monthly_totals["sum_fields_before"] - 1
    ) * 100

    # Monthly aggregates
    out = (
        df2.groupby("month", as_index=False)
        .agg(
            avg_info_gain_pct=("info_gain_pct", "mean"),
            avg_speed_impr_pct=("speed_impr_pct", "mean"),
            avg_speed_delta_sec=("speed_delta_sec", "mean"),
            total_fields_added=("fields_added", "sum"),
        )
        .merge(
            monthly_totals[["month", "weighted_info_gain_pct"]], on="month", how="left"
        )
    )

    return out


# -------------------- MENTORING (dept, type) --------------------
@register_kpi("mentoring")
def compute_mentoring(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expected columns:
      session_id, date, dept, mentoring_type, mentor_hrs, team_time_saved_hrs
    Returns monthly aggregates:
      month, mentor_hrs_sum, team_saved_sum, avg_roi
    """
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


# -------------------- AI ENGAGEMENT (dept usage) --------------------
@register_kpi("ai_engagement")
def compute_ai_engagement(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expected columns:
      month, dept, active_users, ai_calls, survey_score
    Returns monthly aggregates:
      month, total_active_users, total_ai_calls, avg_survey
    """
    df2 = df.copy()
    for c in ["active_users", "ai_calls", "survey_score"]:
        if c in df2.columns:
            df2[c] = pd.to_numeric(df2[c], errors="coerce")
    out = df2.groupby("month", as_index=False).agg(
        total_active_users=("active_users", "sum"),
        total_ai_calls=("ai_calls", "sum"),
        avg_survey=("survey_score", "mean"),
    )
    return out


# -------------------- PROJECT MGMT (MVP delivery) --------------------
@register_kpi("project_mgmt")
def compute_project_mgmt(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expected columns:
      project_name, dept, start_date, mvp_target_date, mvp_actual_date
    Returns a row-per-project with computed fields:
      mvp_cycle_days, on_time (1/0), month (from mvp_actual_date if present else NaT)
    """
    df2 = df.copy()
    for c in ["start_date", "mvp_target_date", "mvp_actual_date"]:
        df2[c] = pd.to_datetime(df2[c], errors="coerce")
    df2["mvp_cycle_days"] = (df2["mvp_actual_date"] - df2["start_date"]).dt.days
    df2["on_time"] = (df2["mvp_actual_date"].notna()) & (
        df2["mvp_actual_date"] <= df2["mvp_target_date"]
    )
    df2["on_time"] = df2["on_time"].astype(int)
    # month for trend (based on actual MVP delivery)
    df2["month"] = df2["mvp_actual_date"].dt.to_period("M").astype("datetime64[ns]")
    return df2


# -------------------- TICKETS (total in range handled in UI) --------------------
@register_kpi("tickets")
def compute_tickets(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"total_tickets_resolved": [len(df)]})


# -------------------- ISSUES (per type monthly) --------------------
@register_kpi("issues")
def compute_issues(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    if "date_closed" in df2.columns:
        df2["month"] = (
            pd.to_datetime(df2["date_closed"], errors="coerce")
            .dt.to_period("M")
            .astype(str)
        )
    return df2.groupby(["month", "type"]).size().unstack(fill_value=0).reset_index()


# -------------------- LEARNING (efficiency + profit) --------------------
@register_kpi("learning")
def compute_learning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expected columns:
      date, skill, implementations, usages, learning_hrs, applied_hrs, profit_over_legacy_pct
    Returns per-month averages:
      avg_efficiency, avg_profit_over_legacy_pct
    """
    df2 = df.copy()
    for c in [
        "implementations",
        "usages",
        "learning_hrs",
        "applied_hrs",
        "profit_over_legacy_pct",
    ]:
        if c in df2.columns:
            df2[c] = pd.to_numeric(df2[c], errors="coerce")
    df2["month"] = (
        pd.to_datetime(df2["date"], errors="coerce").dt.to_period("M").astype(str)
    )
    df2["efficiency"] = df2["applied_hrs"] / df2["learning_hrs"]
    out = df2.groupby("month", as_index=False).agg(
        avg_efficiency=("efficiency", "mean"),
        avg_profit_over_legacy_pct=("profit_over_legacy_pct", "mean"),
    )
    return out


@register_kpi("time_mgmt")
def compute_time_mgmt(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects:
      week_start, kw, development, debugging_tickets, mentoring, devops, project_management, meetings
    Returns per-week:
      week_start (datetime), kw (str), total_hours, and % split per category
    """
    df2 = df.copy()
    # Parse week_start if not already parsed
    if not pd.api.types.is_datetime64_any_dtype(
        df2.get("week_start", pd.Series([], dtype="datetime64[ns]"))
    ):
        df2["week_start"] = pd.to_datetime(df2["week_start"], errors="coerce")

    cats = [
        "development",
        "debugging_tickets",
        "mentoring",
        "devops",
        "project_management",
        "meetings",
    ]
    for c in cats:
        df2[c] = pd.to_numeric(df2.get(c), errors="coerce")

    df2["total_hours"] = df2[cats].sum(axis=1)

    # Percentages (safe: avoid div/0)
    for c in cats:
        df2[f"{c}_pct"] = (df2[c] / df2["total_hours"] * 100).where(
            df2["total_hours"] > 0
        )

    # Keep a clean weekly row (no further grouping; one row per week entry)
    out_cols = ["week_start", "kw", "total_hours"] + cats + [f"{c}_pct" for c in cats]
    out = df2[out_cols].sort_values("week_start")
    return out


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
        "week_start",
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
