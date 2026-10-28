"""
Data Agent — BigQuery interface for the Education Insights system.

Responsibilities
----------------
- Inspect available tables and schemas on request.
- Select and execute the appropriate pre-built parameterized query.
- Fall back to ad-hoc read-only SQL for questions not covered by named queries.
- Return structured results with data-quality caveats clearly stated.
- Accept structured data extracted from uploaded images/PDFs (multimodal path).

This agent never modifies data.  All SQL is read-only.

The agent is not called directly by users.  The root_agent routes qualifying
requests here via the ADK sub-agent mechanism.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from tools.bigquery_tools import (
    get_schema_info,
    get_school_profile,
    list_available_queries,
    run_named_query,
    run_readonly_sql,
)
from tools.multimodal_tools import (
    compare_extracted_with_database,
    extract_data_from_image,
    extract_data_from_pdf,
)

load_dotenv()

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.0-flash")

# ---------------------------------------------------------------------------
# System instruction (injected into the model's context at every turn)
# ---------------------------------------------------------------------------

_INSTRUCTION = """
You are the Data Agent for the Education Insights & Resource Recommender system.

Your role is to translate natural-language questions about California school data
into BigQuery queries and return accurate, structured results.

## Available data
Call get_schema_info() first if you are unsure which tables or columns to use.
Call list_available_queries() to see pre-built query templates before writing SQL.

## Workflow for every request
1. Identify the user's intent: identification, comparison, or recommendation.
2. Call list_available_queries() to check whether a named query matches.
3. If a named query fits, call run_named_query() with appropriate parameters.
4. If no named query fits, call run_readonly_sql() with a hand-crafted SELECT.
   - Always use fully-qualified table references: `project.dataset.table`
   - Use @param_name parameters for filter values — never interpolate user input
5. If the user uploads an image or PDF, call extract_data_from_image() or
   extract_data_from_pdf() first, then optionally compare_extracted_with_database().
6. Return the results as a structured JSON object.  Include any caveats (missing
   values, NULL graduation rates for non-high-schools, etc.) as a 'caveats' list.

## Data quality rules you must always follow
- graduation_rate_pct and college_readiness_pct are NULL for K-5, K-8, and 6-8 schools.
  State this explicitly when those fields appear NULL in your results.
- title_i_funds_usd = 0 (not NULL) for schools that are not Title I eligible.
- stem_program_level: 1=Basic, 2=Moderate, 3=Good, 4=Strong, 5=Exemplary.
- When funding_gap_usd is positive, the school is underfunded relative to state average.
- The dataset covers exactly 30 schools (IDs 1001–1030) in three CA counties:
  Millbrook, Jefferson, Oakdale.  Be explicit if a filter returns fewer schools.

## Never do
- Issue INSERT, UPDATE, DELETE, CREATE, DROP, or any DDL statement.
- Hallucinate data — if a value is not in the dataset, say so.
- Claim statistical causation from correlation (e.g. class size → scores).
  Report correlations and flag them clearly.

## Output format
Return a JSON object with:
{
  "query_name_or_description": "...",
  "result_count": N,
  "data": [...],
  "caveats": ["...", "..."],
  "suggested_next_steps": ["..."]
}
"""

# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

data_agent = Agent(
    name="data_agent",
    model=_MODEL,
    description=(
        "Queries BigQuery to answer data questions about school performance, "
        "funding, staffing, demographics, and programmes. "
        "Routes here for: specific school look-ups, ranked lists, "
        "cross-table joins, uploaded budget documents or report cards."
    ),
    instruction=_INSTRUCTION,
    tools=[
        # Schema exploration
        get_schema_info,
        list_available_queries,
        # Query execution
        run_named_query,
        run_readonly_sql,
        get_school_profile,
        # Multimodal extraction
        extract_data_from_image,
        extract_data_from_pdf,
        compare_extracted_with_database,
    ],
)
