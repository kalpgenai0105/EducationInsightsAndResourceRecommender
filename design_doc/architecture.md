# Education Insights & Resource Recommender — Architecture Design Document

> **Version:** 1.0 · **Date:** October 2026  
> The canonical, rendered version of this document is the HTML artifact published alongside the project.  
> This Markdown copy serves as a plain-text reference for version control.

---

## 1. System Overview

Multi-agent conversational system for 30 California schools across Millbrook, Jefferson, and Oakdale counties. Built on Google ADK, BigQuery, and Vertex AI Agent Engine.

**Primary use-cases:**
- Grant targeting: identify schools with high low-income % and low tech spending
- Programme replication: find high-graduation, low-funding schools as models
- Resource comparison: benchmark any school against county/state averages
- Multimodal: extract data from uploaded budget tables and report cards

---

## 2. Architecture

```
User → Root Agent (education_insights_root)
            ├── Data Agent    → BigQuery (read-only)
            │                 → Gemini Vision (image/PDF extraction)
            └── Insights Agent → Plotly charts + recommendations
```

### Agent responsibilities

| Agent | Role | Tools |
|---|---|---|
| Root | Classify, route, synthesise | — (sub_agents only) |
| Data | BQ queries, multimodal extraction | bigquery_tools, multimodal_tools |
| Insights | Pattern analysis, charts, recommendations | visualization_tools |

### Query classification

- **Identification** → Data Agent only
- **Comparison** → Data Agent → Insights Agent
- **Recommendation** → Data Agent → Insights Agent

---

## 3. Data Model

Five BigQuery tables, all joined on `school_id` (INT64, 1001–1030):

| Table | Key Columns |
|---|---|
| schools_master | low_income_student_pct, total_enrollment, title_i_eligible |
| academic_performance | graduation_rate_pct (HS only), api_score, school_rating |
| funding_resources | per_pupil_funding_usd, per_pupil_tech_spending_usd, funding_gap_usd |
| staffing | avg_class_size, teacher_retention_rate_pct, student_to_counselor_ratio |
| programs_technology | stem_program_level (1–5), broadband_mbps, student_to_device_ratio |

**Caveats:**
- graduation_rate_pct is NULL for K-5, K-8, and 6-8 schools
- title_i_funds_usd = 0 (not NULL) when not eligible
- No geographic coordinates in the dataset

---

## 4. A2A Communication Flow

Single deployment: ADK handles routing internally via `sub_agents`.  
Cross-deployment: Use `RemoteAgent` from `deployment/a2a_config.py`.

```
User → Root → Data Agent → BigQuery
                     ↓
              Insights Agent → Charts (Plotly PNG)
                     ↓
              Root → Final response
```

---

## 5. Security & Privacy

- All SQL uses BigQuery named parameters (`@param_name`) — no injection risk
- `run_readonly_sql()` blocks all DML/DDL keywords before reaching BQ
- Service account holds `bigquery.dataViewer` + `bigquery.jobUser` only
- Production deployments use Workload Identity (no key files)
- Dataset contains no PII — all school-level aggregates

---

## 6. Query Catalog (7 named queries)

| Name | Join Key Tables | Use-case |
|---|---|---|
| low_income_tech_gap | schools_master + funding | Grant targeting |
| high_grad_low_funding | performance + funding + all | Replication models |
| strong_stem_small_classes | programs + staffing + all | STEM model schools |
| counselor_ratio_gap | schools + staffing + funding | Mental-health gap |
| school_comparison | All 5 | Side-by-side comparison |
| technology_equity | schools + programs + funding | Device/broadband gaps |
| improving_schools | schools + performance + funding + staffing | Bright spots |

---

## 7. Limitations

- 30-school sample: too small for statistically robust correlation analysis
- Single-year snapshot — no longitudinal data
- No geographic coordinates — no map views out-of-the-box
- Synthetic data — patterns are plausible but not from real CA records
- No causal inference — the Insights Agent reports correlations only
- Context cap: queries limited to 50 rows to avoid model context overflow
- Image-based PDFs not supported — export pages as images first

---

## 8. Deployment Steps

1. Enable GCP APIs (aiplatform, bigquery, bigquerystorage)
2. Configure `.env` (PROJECT, LOCATION, DATASET)
3. `pip install -r requirements.txt`
4. `python -m data.load_data` — load 5 CSVs into BigQuery
5. `pytest tests/ -v` — 30 offline tests
6. `adk web` — test locally
7. `python -m deployment.deploy_agents` — deploy to Vertex AI Agent Engine
8. `python -m deployment.deploy_agents --test <RESOURCE_NAME>` — smoke test
