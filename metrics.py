import pandas as pd
from typing import Callable, Dict

# Registry for KPI functions
KPI_FUNCTIONS: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {}

# Metadata for each KPI (display name, unit, description, source)
KPI_META: Dict[str, Dict] = {
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
        "display_name": "Learning – Core Skills",
        "unit": "hours",
        "description": "Track invested learning hours by core skill and the technologies/skills added as tags.",
        "source_csv": "learning.csv",
    },
    "time_mgmt": {
        "display_name": "Time Management (Daily Allocation)",
        "unit": "hours",
        "description": "Daily allocation of hours across Development, Debugging/Tickets, Learning, DevOps, Project Management, and Meetings.",
        "source_csv": "time_mgmt.csv",
    },
}




def _normalize_date_series(series: pd.Series) -> pd.Series:
    """Parse mixed date inputs and normalize to datetime64.

    Handles ISO values (YYYY-MM-DD) and common spreadsheet-style values
    like 1/12/2025 (interpreted as day/month/year).
    """
    iso = pd.to_datetime(series, errors="coerce", format="%Y-%m-%d")
    dmy = pd.to_datetime(series, errors="coerce", dayfirst=True)
    return iso.combine_first(dmy)

def register_kpi(name: str):
    def decorator(func: Callable[[pd.DataFrame], pd.DataFrame]):
        KPI_FUNCTIONS[name] = func
        return func

    return decorator


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
    if "time_spent_hrs" not in df2.columns:
        # Backward compatibility with old schema
        df2["time_spent_hrs"] = df2.get("learning_hrs", 0)
    if "core_skill" not in df2.columns:
        df2["core_skill"] = "Uncategorized"
    if "skills_tech_tags" not in df2.columns:
        df2["skills_tech_tags"] = ""
    if "date" not in df2.columns:
        return pd.DataFrame(
            columns=["month", "time_spent_sum", "entries_count", "unique_tech_tags"]
        )

    df2["time_spent_hrs"] = pd.to_numeric(df2["time_spent_hrs"], errors="coerce").fillna(
        0
    )

    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
    df2 = df2.dropna(subset=["date"])
    if df2.empty:
        return pd.DataFrame(
            columns=["month", "time_spent_sum", "entries_count", "unique_tech_tags"]
        )

    df2["month"] = df2["date"].dt.to_period("M").astype(str)

    # monthly aggregates
    out = df2.groupby("month", as_index=False).agg(
        time_spent_sum=("time_spent_hrs", "sum"),
        entries_count=("date", "count"),
        unique_tech_tags=(
            "skills_tech_tags",
            lambda x: len(
                {
                    t.strip().lower()
                    for row in x.dropna().astype(str)
                    for t in row.split(",")
                    if t.strip()
                }
            ),
        ),
    )
    return out


def compute_learning_by_core_skill(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    if "time_spent_hrs" not in df2.columns:
        df2["time_spent_hrs"] = df2.get("learning_hrs", 0)
    if "core_skill" not in df2.columns:
        df2["core_skill"] = "Uncategorized"
    if "skills_tech_tags" not in df2.columns:
        df2["skills_tech_tags"] = ""
    if "date" not in df2.columns:
        return pd.DataFrame(
            columns=["month", "core_skill", "time_spent_sum", "skills_tech_tags"]
        )

    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")
    df2 = df2.dropna(subset=["date"])
    if df2.empty:
        return pd.DataFrame(
            columns=["month", "core_skill", "time_spent_sum", "skills_tech_tags"]
        )

    df2["month"] = df2["date"].dt.to_period("M").astype(str)
    df2["time_spent_hrs"] = pd.to_numeric(df2["time_spent_hrs"], errors="coerce").fillna(0)

    return (
        df2.groupby(["month", "core_skill"], as_index=False)
        .agg(
            time_spent_sum=("time_spent_hrs", "sum"),
            skills_tech_tags=("skills_tech_tags", lambda x: ", ".join(x.dropna().astype(str))),
        )
        .sort_values(["month", "core_skill"])
    )


# -------------------- TIME MGMT (DAILY) --------------------
@register_kpi("time_mgmt")
def compute_time_mgmt(df: pd.DataFrame) -> pd.DataFrame:
    """
    Inputs (daily):
      date, development, debugging_tickets, learning, devops, project_management, meetings
    Output: one row per day with totals and % split.
    """
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"], errors="coerce")

    # Backward compatibility with older CSV schema
    if "learning" not in df2.columns and "mentoring" in df2.columns:
        df2["learning"] = df2["mentoring"]

    cats = [
        "development",
        "debugging_tickets",
        "learning",
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
    df = pd.read_csv(csv_path)

    for col in suggested:
        if col in df.columns:
            df[col] = _normalize_date_series(df[col])

    # Keep month as YYYY-MM string for consistency where applicable.
    if "month" in df.columns:
        month_ts = pd.to_datetime(df["month"], errors="coerce", format="%Y-%m")
        month_ts = month_ts.combine_first(pd.to_datetime(df["month"], errors="coerce", dayfirst=True))
        df["month"] = month_ts.dt.strftime("%Y-%m").where(month_ts.notna(), df["month"])

    return df


def compute_kpi(name: str, df: pd.DataFrame) -> pd.DataFrame:
    if name not in KPI_FUNCTIONS:
        raise KeyError(f"Unknown KPI '{name}'. Available: {list(KPI_FUNCTIONS.keys())}")
    return KPI_FUNCTIONS[name](df)


def list_kpis() -> list:
    return list(KPI_FUNCTIONS.keys())


def get_kpi_meta(name: str) -> dict:
    return KPI_META.get(name, {})
