# Career KPI Dashboard

## Learning CSV schema (simplified)

`learning.csv` now tracks only the fields needed for core-skill learning logs:

- `date`
- `core_skill` (one of the core categories)
- `skills_tech_tags` (comma-separated tags)
- `time_spent_hrs`
- `notes`

Backward compatibility is preserved: if old rows use `learning_hrs`, the app maps it to `time_spent_hrs`.
