"""
Visualisation tool functions exposed to the Insights Agent.

Charts are generated with Plotly (for interactivity when viewed in a browser)
and returned as base64-encoded PNG strings so the agent can embed them in
its response or pass them to a downstream renderer.

Every function accepts a JSON string (the output of a BigQuery tool) so the
agent can pipe data directly from run_named_query() → a chart function.
"""

from __future__ import annotations

import base64
import io
import json
from typing import Any

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fig_to_base64(fig: go.Figure) -> str:
    """Render a Plotly figure to a base64-encoded PNG string."""
    img_bytes = fig.to_image(format="png", width=900, height=500, scale=1.5)
    return base64.b64encode(img_bytes).decode("utf-8")


def _parse_rows(data_json: str) -> list[dict[str, Any]]:
    """Extract the rows list from a run_named_query() JSON response."""
    data = json.loads(data_json)
    if "error" in data:
        raise ValueError(data["error"])
    return data.get("rows", [])


# ---------------------------------------------------------------------------
# Tool: horizontal bar chart — compare schools on one metric
# ---------------------------------------------------------------------------

def bar_chart_schools(
    data_json: str,
    metric_column: str,
    label_column: str = "school_name",
    title: str = "",
    color_by: str | None = None,
) -> str:
    """
    Create a horizontal bar chart comparing schools on a single numeric metric.

    Args:
        data_json: JSON string from run_named_query() containing 'rows'.
        metric_column: The column name to plot on the x-axis.
        label_column: The column to use as y-axis labels (default: school_name).
        title: Chart title. If empty, a default is generated.
        color_by: Optional column name to colour bars (e.g. 'county').

    Returns:
        Base64-encoded PNG string prefixed with 'data:image/png;base64,'.
    """
    rows = _parse_rows(data_json)
    if not rows:
        return "ERROR: No data to chart."

    labels  = [str(r.get(label_column, "")) for r in rows]
    values  = [r.get(metric_column, 0) or 0 for r in rows]
    colors  = [str(r.get(color_by, "")) for r in rows] if color_by else None

    chart_title = title or f"{metric_column.replace('_', ' ').title()} by School"

    fig = px.bar(
        x=values,
        y=labels,
        orientation="h",
        color=colors,
        title=chart_title,
        labels={"x": metric_column.replace("_", " ").title(), "y": ""},
        template="plotly_white",
    )
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        margin=dict(l=200, r=40, t=60, b=40),
        font=dict(size=12),
    )

    b64 = _fig_to_base64(fig)
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Tool: scatter plot — correlation between two metrics
# ---------------------------------------------------------------------------

def scatter_plot(
    data_json: str,
    x_column: str,
    y_column: str,
    label_column: str = "school_name",
    color_by: str | None = "county",
    title: str = "",
    trendline: bool = True,
) -> str:
    """
    Create a scatter plot showing the relationship between two numeric metrics.
    Optionally adds an OLS trendline to indicate correlation direction.

    Args:
        data_json: JSON string from run_named_query().
        x_column: Column name for the x-axis.
        y_column: Column name for the y-axis.
        label_column: Column used for hover labels.
        color_by: Column used to colour points (e.g. 'county').
        title: Chart title.
        trendline: Whether to add an OLS trendline ('ols' requires statsmodels).

    Returns:
        Base64-encoded PNG string.
    """
    rows = _parse_rows(data_json)
    if not rows:
        return "ERROR: No data to chart."

    x_vals    = [r.get(x_column, 0)      for r in rows]
    y_vals    = [r.get(y_column, 0)      for r in rows]
    labels    = [str(r.get(label_column, "")) for r in rows]
    colors    = [str(r.get(color_by, ""))    for r in rows] if color_by else None

    chart_title = title or (
        f"{y_column.replace('_', ' ').title()} vs "
        f"{x_column.replace('_', ' ').title()}"
    )

    fig = go.Figure()

    # One trace per unique colour group
    if colors:
        unique_groups = sorted(set(colors))
        colour_map = px.colors.qualitative.Set2
        for i, group in enumerate(unique_groups):
            mask = [j for j, c in enumerate(colors) if c == group]
            fig.add_trace(go.Scatter(
                x=[x_vals[j] for j in mask],
                y=[y_vals[j] for j in mask],
                mode="markers+text",
                text=[labels[j] for j in mask],
                textposition="top center",
                name=group,
                marker=dict(size=9, color=colour_map[i % len(colour_map)]),
            ))
    else:
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers+text",
            text=labels,
            textposition="top center",
            marker=dict(size=9),
        ))

    if trendline and len(x_vals) > 2:
        try:
            import numpy as np
            coeffs = np.polyfit(
                [v for v in x_vals if v is not None],
                [v for v in y_vals if v is not None],
                1,
            )
            x_range = [min(x_vals), max(x_vals)]
            y_range = [coeffs[0] * v + coeffs[1] for v in x_range]
            fig.add_trace(go.Scatter(
                x=x_range, y=y_range,
                mode="lines",
                name="Trend",
                line=dict(dash="dash", color="grey"),
            ))
        except Exception:
            pass  # trendline is best-effort; skip if numpy unavailable

    fig.update_layout(
        title=chart_title,
        xaxis_title=x_column.replace("_", " ").title(),
        yaxis_title=y_column.replace("_", " ").title(),
        template="plotly_white",
        margin=dict(l=60, r=40, t=60, b=60),
    )

    b64 = _fig_to_base64(fig)
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Tool: grouped multi-metric radar / spider chart for a set of schools
# ---------------------------------------------------------------------------

def radar_chart_schools(
    data_json: str,
    metrics: list[str],
    label_column: str = "school_name",
    title: str = "School Profile Comparison",
) -> str:
    """
    Create a radar chart to compare up to six schools across multiple metrics.

    Each axis is min-max normalised so metrics on different scales are comparable.

    Args:
        data_json: JSON string from run_named_query() (ideally school_comparison).
        metrics: List of numeric column names to include as radar axes.
        label_column: Column used to label each school's trace.
        title: Chart title.

    Returns:
        Base64-encoded PNG string.
    """
    rows = _parse_rows(data_json)
    if not rows:
        return "ERROR: No data to chart."

    rows = rows[:6]  # cap at 6 for readability

    # Min-max normalise each metric across the result set
    def normalise(values: list[float]) -> list[float]:
        mn, mx = min(v for v in values if v is not None), max(v for v in values if v is not None)
        span = mx - mn or 1
        return [((v or 0) - mn) / span for v in values]

    fig = go.Figure()
    colours = px.colors.qualitative.Set2

    for i, row in enumerate(rows):
        raw_vals = [row.get(m, 0) or 0 for m in metrics]
        # Normalise per metric across all rows
        normed_per_metric = [
            normalise([r.get(m, 0) or 0 for r in rows])[i]
            for m in metrics
        ]
        normed_per_metric.append(normed_per_metric[0])  # close the polygon

        fig.add_trace(go.Scatterpolar(
            r=normed_per_metric,
            theta=metrics + [metrics[0]],
            fill="toself",
            name=str(row.get(label_column, f"School {i+1}")),
            line=dict(color=colours[i % len(colours)]),
            opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        title=title,
        template="plotly_white",
    )

    b64 = _fig_to_base64(fig)
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Tool: county-level summary bar chart
# ---------------------------------------------------------------------------

def county_summary_chart(
    data_json: str,
    metric_column: str,
    agg: str = "mean",
    title: str = "",
) -> str:
    """
    Aggregate a numeric metric by county and render as a bar chart.

    Args:
        data_json: JSON string from run_named_query().
        metric_column: Numeric column to aggregate.
        agg: Aggregation function — 'mean', 'sum', or 'count'.
        title: Chart title.

    Returns:
        Base64-encoded PNG string.
    """
    rows = _parse_rows(data_json)
    if not rows:
        return "ERROR: No data to chart."

    from collections import defaultdict

    buckets: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        county = str(r.get("county", "Unknown"))
        val = r.get(metric_column)
        if val is not None:
            buckets[county].append(float(val))

    if not buckets:
        return "ERROR: 'county' column not found in result set."

    counties = sorted(buckets.keys())
    if agg == "mean":
        agg_vals = [sum(buckets[c]) / len(buckets[c]) for c in counties]
    elif agg == "sum":
        agg_vals = [sum(buckets[c]) for c in counties]
    else:  # count
        agg_vals = [len(buckets[c]) for c in counties]

    chart_title = title or f"{agg.title()} {metric_column.replace('_', ' ').title()} by County"

    fig = px.bar(
        x=counties, y=agg_vals,
        title=chart_title,
        labels={"x": "County", "y": f"{agg.title()} {metric_column}"},
        color=counties,
        template="plotly_white",
    )
    fig.update_layout(showlegend=False)

    b64 = _fig_to_base64(fig)
    return f"data:image/png;base64,{b64}"


# ---------------------------------------------------------------------------
# Tool: generate all standard charts for a query result in one call
# ---------------------------------------------------------------------------

def generate_insight_charts(
    data_json: str,
    query_name: str,
) -> str:
    """
    Generate a standard set of charts appropriate for the given query type.

    Returns a JSON object mapping chart type to base64 PNG string.
    Use this when you want a full visual package without specifying individual charts.

    Args:
        data_json: JSON string from run_named_query().
        query_name: The query that produced the data (used to select chart types).

    Returns:
        JSON string: {"charts": {"bar": "data:image/png;...", "scatter": "..."}}
    """
    chart_configs: dict[str, dict[str, Any]] = {
        "low_income_tech_gap": {
            "bar":     {"metric_column": "per_pupil_tech_spending_usd", "color_by": "county"},
            "scatter": {"x_column": "low_income_student_pct", "y_column": "per_pupil_tech_spending_usd"},
        },
        "high_grad_low_funding": {
            "bar":     {"metric_column": "graduation_rate_pct", "color_by": "county"},
            "scatter": {"x_column": "per_pupil_funding_usd", "y_column": "graduation_rate_pct"},
        },
        "strong_stem_small_classes": {
            "bar":     {"metric_column": "stem_program_level"},
            "scatter": {"x_column": "avg_class_size", "y_column": "math_proficiency_pct"},
        },
        "school_comparison": {
            "radar":   {"metrics": ["math_proficiency_pct", "teacher_retention_rate_pct",
                                    "per_pupil_funding_usd", "stem_program_level",
                                    "broadband_mbps"]},
        },
        "technology_equity": {
            "bar":     {"metric_column": "student_to_device_ratio"},
            "scatter": {"x_column": "per_pupil_tech_spending_usd", "y_column": "broadband_mbps"},
        },
    }

    config = chart_configs.get(query_name, {
        "bar": {"metric_column": "api_score"},
    })

    results: dict[str, str] = {}

    if "bar" in config:
        try:
            results["bar"] = bar_chart_schools(data_json, **config["bar"])
        except Exception as exc:
            results["bar"] = f"ERROR: {exc}"

    if "scatter" in config:
        try:
            results["scatter"] = scatter_plot(data_json, **config["scatter"])
        except Exception as exc:
            results["scatter"] = f"ERROR: {exc}"

    if "radar" in config:
        try:
            results["radar"] = radar_chart_schools(data_json, **config["radar"])
        except Exception as exc:
            results["radar"] = f"ERROR: {exc}"

    return json.dumps({"charts": results})
