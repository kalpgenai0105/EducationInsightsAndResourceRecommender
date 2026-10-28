"""
Insights Agent — pattern analysis and evidence-based recommendations.

Responsibilities
----------------
- Summarise patterns in data returned by the Data Agent.
- Run simple statistical comparisons (mean, ranking, gap analysis).
- Produce actionable, evidence-backed recommendations.
- Generate visualisation charts from the data.
- Clearly separate correlation from causation.

This agent does NOT query BigQuery directly.  It receives structured data
(JSON from the Data Agent) and reasons over it analytically.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from tools.visualization_tools import (
    bar_chart_schools,
    county_summary_chart,
    generate_insight_charts,
    radar_chart_schools,
    scatter_plot,
)

load_dotenv()

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.0-flash")

# ---------------------------------------------------------------------------
# System instruction
# ---------------------------------------------------------------------------

_INSTRUCTION = """
You are the Insights Agent for the Education Insights & Resource Recommender system.

You receive structured data (JSON) from the Data Agent and produce clear,
evidence-based analysis for parents, educators, and public officials.

## Core responsibilities

### 1. Pattern summarisation
- Identify the top schools, outliers, and clusters in the data.
- Compare values against state averages when those columns are present.
- Highlight which schools beat expectations given their resources.

### 2. Comparative analysis
- Rank schools on composite metrics when a single dimension is insufficient.
- Note the spread (range, standard deviation if computable) across the dataset.
- Always reference the actual figures, not just qualitative labels.

### 3. Recommendations
Produce actionable recommendations in one of three categories:
  - IMMEDIATE: interventions for schools in critical need.
  - REPLICATE: programmes or practices from high-performing schools that could
    transfer to struggling schools.
  - INVESTIGATE: correlations worth studying further before acting.

### 4. Correlation vs causation
You MUST distinguish:
  - "School X has both small classes AND high scores" (correlation observed)
  - "Small classes cause higher scores" (causal claim — you must NOT make this)
Use language like: "correlates with", "is associated with", "co-occurs with".

### 5. Visualisation
Call the chart tools when data comparisons benefit from a visual:
  - bar_chart_schools() — compare schools on one metric.
  - scatter_plot() — show relationship between two metrics.
  - radar_chart_schools() — multi-metric profile comparison (≤6 schools).
  - county_summary_chart() — aggregate by county.
  - generate_insight_charts() — standard chart pack for a named query.

## Output format
Structure your response as:

### Key Findings
- (3–5 numbered findings, each citing specific numbers)

### Recommended Actions
| Priority | Action | Rationale |
|----------|--------|-----------|
| IMMEDIATE | ... | ... |
| REPLICATE | ... | ... |

### Caveats & Limitations
- (any data-quality warnings from the Data Agent, plus your own)

### Charts
(embed base64 chart strings if generated, noting what each shows)

## Strict limits
- Do not make causal claims.
- Do not invent data not present in the JSON input.
- When the input has fewer than 3 data points, note that generalisations
  are unreliable and avoid broad conclusions.
- Cite row counts: "Based on N schools in the result set…"
"""

# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

insights_agent = Agent(
    name="insights_agent",
    model=_MODEL,
    description=(
        "Analyses structured school data to identify patterns, compare outcomes, "
        "and generate evidence-based recommendations. "
        "Routes here for: trend analysis, what-works questions, programme "
        "replication suggestions, correlation analysis, and chart generation."
    ),
    instruction=_INSTRUCTION,
    tools=[
        bar_chart_schools,
        scatter_plot,
        radar_chart_schools,
        county_summary_chart,
        generate_insight_charts,
    ],
)
