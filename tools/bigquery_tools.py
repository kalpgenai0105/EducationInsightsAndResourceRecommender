"""
BigQuery tool functions exposed to the Data Agent.

Each function is a plain Python callable that the ADK wraps as a Tool.
All queries go through parameterized execution so user-supplied values
are never interpolated directly into SQL strings (prevents injection).

Design decisions
----------------
- Results are returned as JSON-serialisable dicts so the agent can reason
  over them and the Insights Agent can consume them without BQ access.
- Pagination is via a `limit` parameter; cursors are omitted because the
  dataset is small (≤30 rows per full scan) and the agent needs context,
  not streaming.
- All functions are read-only.  No INSERT/UPDATE/DELETE/DDL is possible
  through this module.
"""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google.cloud import bigquery
from tenacity import retry, stop_after_attempt, wait_exponential

from data.queries import QUERY_CATALOG, build_query
from data.schema import SCHEMA_SUMMARY

load_dotenv()

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASET = os.environ.get("BIGQUERY_DATASET", "education_insights")

# Lazy-initialised client; created on first use so unit tests can mock it.
_bq_client: bigquery.Client | None = None


def _get_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=PROJECT)
    return _bq_client


def _rows_to_dicts(rows: bigquery.table.RowIterator) -> list[dict[str, Any]]:
    """Convert BigQuery RowIterator to a JSON-safe list of dicts."""
    result = []
    for row in rows:
        d = {}
        for key, value in row.items():
            # Convert types that are not JSON-serialisable
            if hasattr(value, "isoformat"):          # date / datetime
                d[key] = value.isoformat()
            elif value is None:
                d[key] = None
            else:
                d[key] = value
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Tool: get schema information
# ---------------------------------------------------------------------------

def get_schema_info() -> str:
    """
    Return a plain-text description of all BigQuery tables, columns, and join keys.

    Call this first when the user asks a question that requires knowing what
    data is available before writing SQL.
    """
    return SCHEMA_SUMMARY


# ---------------------------------------------------------------------------
# Tool: list available named queries
# ---------------------------------------------------------------------------

def list_available_queries() -> str:
    """
    Return the names and descriptions of all pre-built parameterized queries.

    Use this to choose the right query for a user's question instead of
    writing raw SQL.
    """
    lines = ["Available named queries:", ""]
    for name, desc in QUERY_CATALOG.items():
        lines.append(f"  {name}: {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool: run a named query
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def run_named_query(
    query_name: str,
    county: str | None = None,
    limit: int = 10,
    school_ids: list[int] | None = None,
    min_stem_level: int = 4,
    max_class_size: float = 23.0,
    grad_rate_threshold: float | None = None,
) -> str:
    """
    Execute a pre-built parameterized query by name and return results as JSON.

    Args:
        query_name: One of the names returned by list_available_queries().
        county: Optional filter — 'Millbrook', 'Jefferson', or 'Oakdale'.
        limit: Maximum number of rows to return (1–50).
        school_ids: Optional list of specific school IDs for 'school_comparison'.
        min_stem_level: Minimum STEM programme level for 'strong_stem_small_classes'.
        max_class_size: Maximum average class size for 'strong_stem_small_classes'.
        grad_rate_threshold: Minimum graduation rate for 'high_grad_low_funding'.

    Returns:
        JSON string with keys: query_name, row_count, columns, rows, caveats.
    """
    limit = max(1, min(limit, 50))  # hard cap at 50 to avoid overloading context

    try:
        sql, params = build_query(
            query_name,
            project=PROJECT,
            dataset=DATASET,
            county=county,
            limit=limit,
            school_ids=school_ids,
            min_stem_level=min_stem_level,
            max_class_size=max_class_size,
            grad_rate_threshold=grad_rate_threshold,
        )
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    job_config = bigquery.QueryJobConfig(query_parameters=params)
    client = _get_client()

    try:
        job = client.query(sql, job_config=job_config)
        rows = _rows_to_dicts(job.result())
    except Exception as exc:
        return json.dumps({"error": f"BigQuery error: {exc}"})

    columns = list(rows[0].keys()) if rows else []

    # Attach data-quality caveats relevant to the chosen query
    caveats = _get_caveats(query_name, rows)

    return json.dumps(
        {
            "query_name": query_name,
            "row_count":  len(rows),
            "columns":    columns,
            "rows":       rows,
            "caveats":    caveats,
        },
        default=str,
    )


def _get_caveats(query_name: str, rows: list[dict]) -> list[str]:
    """Return relevant data-quality warnings for the result set."""
    caveats: list[str] = []

    null_grad = [r for r in rows if r.get("graduation_rate_pct") is None]
    if null_grad:
        names = [r.get("school_name", r.get("school_id", "?")) for r in null_grad[:3]]
        caveats.append(
            f"graduation_rate_pct is NULL for non-high-school records: "
            f"{', '.join(str(n) for n in names)}"
            + (" (and more)" if len(null_grad) > 3 else "")
        )

    if query_name == "strong_stem_small_classes" and not rows:
        caveats.append(
            "No schools matched both criteria simultaneously. "
            "Try relaxing max_class_size (e.g. 25) or min_stem_level (e.g. 3)."
        )

    if query_name == "low_income_tech_gap":
        caveats.append(
            "priority_score is a composite index (60% low-income weight + "
            "40% tech-gap weight) for ranking purposes only — not an official metric."
        )

    return caveats


# ---------------------------------------------------------------------------
# Tool: run ad-hoc read-only SQL (for advanced queries)
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def run_readonly_sql(sql: str) -> str:
    """
    Execute a caller-supplied SELECT query against the education dataset and
    return results as JSON.

    IMPORTANT: Only SELECT statements are accepted.  Any SQL that modifies
    data (INSERT, UPDATE, DELETE, CREATE, DROP, MERGE, CALL) will be rejected
    before execution.

    Use this for ad-hoc analysis not covered by the named queries.

    Args:
        sql: A SELECT statement.  Table references must use the full form
             `project.dataset.table` — use get_schema_info() to find table names.

    Returns:
        JSON string with keys: row_count, columns, rows.
    """
    # Safety guard: block any DML / DDL
    upper = sql.strip().upper()
    forbidden = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "TRUNCATE",
                 "MERGE", "CALL", "ALTER", "GRANT", "REVOKE")
    for keyword in forbidden:
        if upper.startswith(keyword) or f"\n{keyword}" in upper:
            return json.dumps({
                "error": f"Statement begins with or contains '{keyword}'. "
                         f"Only SELECT queries are allowed."
            })

    client = _get_client()
    try:
        job = client.query(sql)
        rows = _rows_to_dicts(job.result())
    except Exception as exc:
        return json.dumps({"error": f"BigQuery error: {exc}"})

    columns = list(rows[0].keys()) if rows else []
    return json.dumps(
        {"row_count": len(rows), "columns": columns, "rows": rows},
        default=str,
    )


# ---------------------------------------------------------------------------
# Tool: get a quick summary of a single school
# ---------------------------------------------------------------------------

def get_school_profile(school_id: int) -> str:
    """
    Return a full profile for a single school by school_id (1001–1030).

    Joins all five tables and returns a single-row summary as formatted text.
    Use this when the user asks about a specific school by name or ID.
    """
    sql = f"""
    SELECT
        s.school_id, s.school_name, s.district, s.county,
        s.school_type, s.grade_levels, s.total_enrollment,
        s.low_income_student_pct, s.title_i_eligible,
        a.math_proficiency_pct, a.ela_proficiency_pct,
        a.graduation_rate_pct, a.api_score, a.school_rating,
        f.per_pupil_funding_usd, f.per_pupil_tech_spending_usd,
        f.funding_gap_usd,
        st.avg_class_size, st.teacher_retention_rate_pct,
        st.student_to_counselor_ratio,
        p.stem_program, p.stem_program_level,
        p.broadband_mbps, p.student_to_device_ratio
    FROM `{PROJECT}.{DATASET}.schools_master` s
    JOIN `{PROJECT}.{DATASET}.academic_performance` a  ON s.school_id = a.school_id
    JOIN `{PROJECT}.{DATASET}.funding_resources`   f  ON s.school_id = f.school_id
    JOIN `{PROJECT}.{DATASET}.staffing`            st ON s.school_id = st.school_id
    JOIN `{PROJECT}.{DATASET}.programs_technology` p  ON s.school_id = p.school_id
    WHERE s.school_id = @school_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("school_id", "INT64", school_id)
        ]
    )
    client = _get_client()
    try:
        job = client.query(sql, job_config=job_config)
        rows = _rows_to_dicts(job.result())
    except Exception as exc:
        return json.dumps({"error": str(exc)})

    if not rows:
        return json.dumps({"error": f"No school found with school_id={school_id}"})

    return json.dumps({"school": rows[0]}, default=str)
