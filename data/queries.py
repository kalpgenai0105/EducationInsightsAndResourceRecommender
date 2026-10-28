"""
Parameterized, read-only BigQuery SQL templates for the Education Insights system.

All queries use BigQuery named parameters (@param_name) for user-supplied values
and Python f-strings only for the project/dataset table references (which are
controlled values from config, never from user input).

Usage:
    from data.queries import build_query, QUERY_CATALOG
    sql, params = build_query("low_income_tech_gap", county="Millbrook", limit=5)
"""

from __future__ import annotations
from typing import Any
from google.cloud import bigquery


def _table(project: str, dataset: str, table: str) -> str:
    """Return a fully-qualified, backtick-quoted BigQuery table reference."""
    return f"`{project}.{dataset}.{table}`"


def build_query(
    query_name: str,
    project: str,
    dataset: str,
    **kwargs: Any,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    """
    Return (sql_string, query_parameters) for the named query template.

    The caller passes named keyword arguments that become BigQuery @parameters.
    Table references are injected via f-string (safe: they come from config,
    not user input) while all filter values go through parameterized binding
    to prevent injection.
    """
    builder = _QUERY_BUILDERS.get(query_name)
    if builder is None:
        raise ValueError(
            f"Unknown query '{query_name}'. "
            f"Available: {sorted(_QUERY_BUILDERS.keys())}"
        )
    return builder(project, dataset, **kwargs)


# ---------------------------------------------------------------------------
# Query 1: Schools with highest low-income % AND lowest tech spending
# Use-case: grant-funding prioritisation
# ---------------------------------------------------------------------------
def _low_income_tech_gap(
    project: str,
    dataset: str,
    county: str | None = None,
    limit: int = 5,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    fr = _table(project, dataset, "funding_resources")

    county_filter = "AND s.county = @county" if county else ""

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.total_enrollment,
        s.low_income_student_pct,
        s.free_reduced_lunch_pct,
        s.title_i_eligible,
        f.per_pupil_funding_usd,
        f.per_pupil_tech_spending_usd,
        f.tech_spending_gap_usd,
        f.funding_gap_usd,
        -- Composite priority score: high low-income weight plus low tech penalty
        ROUND(
            (s.low_income_student_pct * 0.6)
            + ((f.state_avg_tech_spending_usd - f.per_pupil_tech_spending_usd) / f.state_avg_tech_spending_usd * 100 * 0.4),
            2
        ) AS priority_score
    FROM {sm} s
    JOIN {fr} f ON s.school_id = f.school_id
    WHERE 1=1
    {county_filter}
    ORDER BY priority_score DESC
    LIMIT @limit
    """

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if county:
        params.append(bigquery.ScalarQueryParameter("county", "STRING", county))

    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 2: High graduation rate despite below-average funding
# Use-case: identify replicable programme models
# ---------------------------------------------------------------------------
def _high_grad_low_funding(
    project: str,
    dataset: str,
    grad_rate_threshold: float | None = None,
    limit: int = 10,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    ap = _table(project, dataset, "academic_performance")
    fr = _table(project, dataset, "funding_resources")
    pt = _table(project, dataset, "programs_technology")
    st = _table(project, dataset, "staffing")

    # Use the caller's threshold if provided, otherwise use the state average
    grad_filter = (
        "AND a.graduation_rate_pct >= @grad_threshold"
        if grad_rate_threshold is not None
        else "AND a.graduation_rate_pct > a.state_avg_graduation_rate_pct"
    )

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.school_type,
        s.total_enrollment,
        s.low_income_student_pct,
        a.graduation_rate_pct,
        a.state_avg_graduation_rate_pct,
        ROUND(a.graduation_rate_pct - a.state_avg_graduation_rate_pct, 1)
            AS grad_rate_above_avg,
        f.per_pupil_funding_usd,
        f.state_avg_per_pupil_funding_usd,
        f.funding_gap_usd,
        a.college_readiness_pct,
        a.api_score,
        p.stem_program_level,
        st.avg_class_size,
        st.teacher_retention_rate_pct
    FROM {ap} a
    JOIN {fr} f  ON a.school_id = f.school_id
    JOIN {sm} s  ON a.school_id = s.school_id
    JOIN {pt} p  ON a.school_id = p.school_id
    JOIN {st} st ON a.school_id = st.school_id
    WHERE a.graduation_rate_pct IS NOT NULL
      AND f.per_pupil_funding_usd < f.state_avg_per_pupil_funding_usd
    {grad_filter}
    ORDER BY grad_rate_above_avg DESC, f.funding_gap_usd DESC
    LIMIT @limit
    """

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if grad_rate_threshold is not None:
        params.append(
            bigquery.ScalarQueryParameter("grad_threshold", "FLOAT64", grad_rate_threshold)
        )

    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 3: Strong STEM programmes with small class sizes
# Use-case: find schools to model STEM rollout
# ---------------------------------------------------------------------------
def _strong_stem_small_classes(
    project: str,
    dataset: str,
    min_stem_level: int = 4,
    max_class_size: float = 23.0,
    limit: int = 10,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    pt = _table(project, dataset, "programs_technology")
    st = _table(project, dataset, "staffing")
    ap = _table(project, dataset, "academic_performance")

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.school_type,
        s.grade_levels,
        p.stem_program,
        p.stem_program_level,
        p.robotics_club,
        p.coding_classes,
        p.advanced_placement_courses,
        p.broadband_mbps,
        p.student_to_device_ratio,
        st.avg_class_size,
        st.stem_certified_teachers,
        st.teacher_retention_rate_pct,
        a.math_proficiency_pct,
        a.science_proficiency_pct,
        a.api_score
    FROM {pt} p
    JOIN {st} st ON p.school_id = st.school_id
    JOIN {sm} s  ON p.school_id = s.school_id
    JOIN {ap} a  ON p.school_id = a.school_id
    WHERE p.stem_program_level >= @min_stem_level
      AND st.avg_class_size    <= @max_class_size
    ORDER BY p.stem_program_level DESC, st.avg_class_size ASC
    LIMIT @limit
    """

    params = [
        bigquery.ScalarQueryParameter("min_stem_level", "INT64",   min_stem_level),
        bigquery.ScalarQueryParameter("max_class_size", "FLOAT64", max_class_size),
        bigquery.ScalarQueryParameter("limit",          "INT64",   limit),
    ]
    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 4: Staffing parity — schools with high student-to-counselor ratios
# Use-case: mental-health resource gap analysis
# ---------------------------------------------------------------------------
def _counselor_ratio_gap(
    project: str,
    dataset: str,
    county: str | None = None,
    limit: int = 10,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    st = _table(project, dataset, "staffing")
    fr = _table(project, dataset, "funding_resources")

    county_filter = "AND s.county = @county" if county else ""

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.total_enrollment,
        s.low_income_student_pct,
        st.student_to_counselor_ratio,
        st.avg_class_size,
        st.teacher_retention_rate_pct,
        st.teacher_vacancies,
        f.per_pupil_funding_usd,
        f.counseling_budget_usd,
        ROUND(f.counseling_budget_usd / NULLIF(s.total_enrollment, 0), 2)
            AS counseling_spend_per_pupil
    FROM {sm} s
    JOIN {st} st ON s.school_id = st.school_id
    JOIN {fr} f  ON s.school_id = f.school_id
    WHERE 1=1
    {county_filter}
    ORDER BY st.student_to_counselor_ratio DESC
    LIMIT @limit
    """

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if county:
        params.append(bigquery.ScalarQueryParameter("county", "STRING", county))

    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 5: Compare schools across all key metrics (multi-dimensional view)
# Use-case: holistic comparison for a list of school IDs
# ---------------------------------------------------------------------------
def _school_comparison(
    project: str,
    dataset: str,
    school_ids: list[int] | None = None,
    county: str | None = None,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    ap = _table(project, dataset, "academic_performance")
    fr = _table(project, dataset, "funding_resources")
    st = _table(project, dataset, "staffing")
    pt = _table(project, dataset, "programs_technology")

    # Build an UNNEST array parameter if specific IDs are requested
    id_filter = ""
    params: list[bigquery.ScalarQueryParameter] = []

    if school_ids:
        id_filter = "AND s.school_id IN UNNEST(@school_ids)"
        params.append(
            bigquery.ArrayQueryParameter("school_ids", "INT64", school_ids)
        )
    if county:
        id_filter += " AND s.county = @county"
        params.append(bigquery.ScalarQueryParameter("county", "STRING", county))

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.school_type,
        s.grade_levels,
        s.total_enrollment,
        s.low_income_student_pct,
        s.title_i_eligible,
        a.math_proficiency_pct,
        a.ela_proficiency_pct,
        a.graduation_rate_pct,
        a.api_score,
        a.school_rating,
        f.per_pupil_funding_usd,
        f.per_pupil_tech_spending_usd,
        f.funding_gap_usd,
        st.avg_class_size,
        st.teacher_retention_rate_pct,
        st.student_to_counselor_ratio,
        pt.stem_program_level,
        pt.broadband_mbps,
        pt.student_to_device_ratio
    FROM {sm} s
    JOIN {ap} a  ON s.school_id = a.school_id
    JOIN {fr} f  ON s.school_id = f.school_id
    JOIN {st} st ON s.school_id = st.school_id
    JOIN {pt} pt ON s.school_id = pt.school_id
    WHERE 1=1
    {id_filter}
    ORDER BY s.school_id
    """

    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 6: Technology equity — device and broadband gaps
# ---------------------------------------------------------------------------
def _technology_equity(
    project: str,
    dataset: str,
    county: str | None = None,
    limit: int = 30,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    pt = _table(project, dataset, "programs_technology")
    fr = _table(project, dataset, "funding_resources")

    county_filter = "AND s.county = @county" if county else ""

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.county,
        s.low_income_student_pct,
        p.student_to_device_ratio,
        p.broadband_mbps,
        p.avg_device_age_years,
        p.avg_tech_uptime_pct,
        f.per_pupil_tech_spending_usd,
        f.tech_spending_gap_usd,
        -- Equity tier: 1=Critical, 2=Needs attention, 3=Adequate, 4=Strong
        CASE
            WHEN p.student_to_device_ratio > 3 OR p.broadband_mbps < 50  THEN 'Critical'
            WHEN p.student_to_device_ratio > 2 OR p.broadband_mbps < 100 THEN 'Needs Attention'
            WHEN p.student_to_device_ratio > 1.5                          THEN 'Adequate'
            ELSE 'Strong'
        END AS tech_equity_tier
    FROM {sm} s
    JOIN {pt} p ON s.school_id = p.school_id
    JOIN {fr} f ON s.school_id = f.school_id
    WHERE 1=1
    {county_filter}
    ORDER BY p.student_to_device_ratio DESC, p.broadband_mbps ASC
    LIMIT @limit
    """

    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]
    if county:
        params.append(bigquery.ScalarQueryParameter("county", "STRING", county))

    return sql.strip(), params


# ---------------------------------------------------------------------------
# Query 7: Year-over-year improving schools with limited resources
# Use-case: resilience / bright-spots analysis
# ---------------------------------------------------------------------------
def _improving_schools(
    project: str,
    dataset: str,
    limit: int = 10,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    sm = _table(project, dataset, "schools_master")
    ap = _table(project, dataset, "academic_performance")
    fr = _table(project, dataset, "funding_resources")
    st = _table(project, dataset, "staffing")

    sql = f"""
    SELECT
        s.school_id,
        s.school_name,
        s.district,
        s.county,
        s.low_income_student_pct,
        a.api_score,
        a.school_rating,
        a.year_over_year_improvement,
        f.per_pupil_funding_usd,
        f.funding_gap_usd,
        st.teacher_retention_rate_pct,
        st.avg_class_size
    FROM {sm} s
    JOIN {ap} a  ON s.school_id = a.school_id
    JOIN {fr} f  ON s.school_id = f.school_id
    JOIN {st} st ON s.school_id = st.school_id
    WHERE a.year_over_year_improvement = 'Yes'
      AND f.per_pupil_funding_usd < f.state_avg_per_pupil_funding_usd
    ORDER BY s.low_income_student_pct DESC, a.api_score DESC
    LIMIT @limit
    """

    params = [bigquery.ScalarQueryParameter("limit", "INT64", limit)]
    return sql.strip(), params


# ---------------------------------------------------------------------------
# Internal registry: name → builder function
# ---------------------------------------------------------------------------
_QUERY_BUILDERS = {
    "low_income_tech_gap":     _low_income_tech_gap,
    "high_grad_low_funding":   _high_grad_low_funding,
    "strong_stem_small_classes": _strong_stem_small_classes,
    "counselor_ratio_gap":     _counselor_ratio_gap,
    "school_comparison":       _school_comparison,
    "technology_equity":       _technology_equity,
    "improving_schools":       _improving_schools,
}

# Public catalog — used by the Data Agent's tool description
QUERY_CATALOG: dict[str, str] = {
    "low_income_tech_gap":       "Schools with highest low-income % and lowest tech spending (grant targeting)",
    "high_grad_low_funding":     "High graduation rate despite below-average per-pupil funding (replication models)",
    "strong_stem_small_classes": "Strong STEM programmes (level ≥4) combined with small class sizes",
    "counselor_ratio_gap":       "Schools with the highest student-to-counselor ratios (mental-health gap)",
    "school_comparison":         "Side-by-side multi-metric comparison of one or more schools",
    "technology_equity":         "Device ratios and broadband gaps by school (tech equity tiers)",
    "improving_schools":         "Year-over-year improving schools that are still below-average funded",
}
