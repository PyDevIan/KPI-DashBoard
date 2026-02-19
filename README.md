# Career KPI Dashboard

## Learning CSV schema (revamped)

`learning.csv` now supports core skill tracking with hours and learned technologies/tags:

- `date`
- `core_skill` (one of the core categories)
- `skills_tech_tags` (comma-separated tags)
- `time_spent_hrs`
- `applied_hrs`
- `applications`
- `delta_performance_pct`
- `time_saved_hrs`
- `cost_eur`
- `notes`

Backward compatibility is preserved: if old rows use `learning_hrs`, the app maps it to `time_spent_hrs`.
