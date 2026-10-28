# Education Insights & Resource Recommender

A production-quality multi-agent conversational system built with **Google Agent Development Kit (ADK)**, **BigQuery**, and **Vertex AI Agent Engine**.

The system helps parents, educators, and public officials turn static government school data into actionable answers about performance, resource allocation, staffing parity, and funding disparities across 30 California schools.

---

## Schema Assumptions

> The `sample_data/` files were the source of truth. The following assumptions
> were made and documented here for transparency:

| Assumption | Rationale |
|---|---|
| `graduation_rate_pct` is NULL for K-5, K-8, and 6-8 schools | The CSV confirms empty values for non-high-school rows |
| `title_i_funds_usd = 0` (not NULL) when not eligible | All non-eligible schools have `0` in the CSV |
| `stem_program_level` 1–5 maps to Basic/Moderate/Good/Strong/Exemplary | Confirmed by `programs_technology.csv` |
| No geographic coordinates are present | Map views require an external geocoding step |
| Dataset is static (no live feed) | Re-run `load_data.py` to refresh after any CSV update |

---

## Project Structure

```
CapstoneProject/
├── agents/
│   ├── __init__.py           # Exports root_agent as `agent`
│   ├── root_agent.py         # Entry point; classifies & routes queries
│   ├── data_agent.py         # BigQuery queries + multimodal extraction
│   └── insights_agent.py     # Pattern analysis, charts, recommendations
├── tools/
│   ├── bigquery_tools.py     # BQ execution helpers (all read-only)
│   ├── visualization_tools.py # Plotly chart generators
│   └── multimodal_tools.py   # Image/PDF extraction via Gemini vision
├── data/
│   ├── schema.py             # BigQuery SchemaField definitions
│   ├── queries.py            # Parameterized SQL templates
│   └── load_data.py          # CSV → BigQuery loader
├── deployment/
│   ├── deploy_agents.py      # Vertex AI Agent Engine deployment
│   └── a2a_config.py         # A2A topology and agent cards
├── tests/
│   ├── test_queries.py       # SQL builder + schema tests (offline)
│   └── test_agents.py        # Agent + tool integration tests (mocked BQ)
├── sample_data/              # 30-school CA dataset (5 CSV files)
├── design_doc/
│   └── architecture.md       # Architecture & design document
├── requirements.txt
├── pyproject.toml
└── .env.example
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Tested on 3.11 and 3.12 |
| Google Cloud SDK (`gcloud`) | latest | For authentication |
| GCP project | — | With billing enabled |
| APIs enabled | — | See step 2 below |

### GCP APIs to enable

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  bigquery.googleapis.com \
  bigquerystorage.googleapis.com \
  storage.googleapis.com
```

---

## Environment Setup

### 1. Clone / navigate to the project

```bash
cd CapstoneProject
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
BIGQUERY_DATASET=education_insights
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

### 5. Authenticate (choose one)

**Option A — Service account key (local dev):**
```bash
export GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json
```

**Option B — Application Default Credentials (recommended):**
```bash
gcloud auth application-default login
gcloud config set project your-project-id
```

---

## Loading Data into BigQuery

### Validate CSVs first (no upload)

```bash
python -m data.load_data --dry-run
```

### Load all tables

```bash
python -m data.load_data
```

### Refresh (drop and recreate all tables)

```bash
python -m data.load_data --replace
```

### Load a single table

```bash
python -m data.load_data --table staffing
```

Expected output:
```
Created dataset your-project.education_insights
Loaded 30 rows → your-project.education_insights.schools_master
Loaded 30 rows → your-project.education_insights.academic_performance
...
Done. 150 total rows loaded.
```

---

## Running Locally (ADK Dev Server)

The ADK CLI provides a web chat UI for local testing:

```bash
adk web
```

Then open [http://localhost:8000](http://localhost:8000) and select `education_insights_root`.

Or run from the command line:

```bash
adk run agents
```

### Example queries to try locally

```
1. Identify the five schools in Millbrook County with the highest rate of
   low-income students and the lowest per-pupil technology spending.

2. Find schools with high graduation rates despite below-average funding,
   to discover effective programme models that can be replicated.

3. Find schools with strong STEM programmes and low class sizes.

4. Compare Summit Ridge High School and Harmony Valley High on graduation
   rates, funding, and teacher retention.

5. Which county has the worst student-to-counselor ratios?
```

---

## Deploying to Vertex AI Agent Engine

### 1. Deploy

```bash
python -m deployment.deploy_agents
```

The script prints the resource name on success:
```
Deployed successfully.
Resource name: projects/YOUR_PROJECT/locations/us-central1/reasoningEngines/123456789
```

Add it to `.env`:
```env
AGENT_ENGINE_RESOURCE_NAME=projects/YOUR_PROJECT/locations/us-central1/reasoningEngines/123456789
```

### 2. Smoke-test the deployment

```bash
python -m deployment.deploy_agents --test projects/YOUR_PROJECT/locations/us-central1/reasoningEngines/123456789
```

### 3. List all deployments

```bash
python -m deployment.deploy_agents --list
```

### 4. Delete a deployment

```bash
python -m deployment.deploy_agents --delete projects/.../reasoningEngines/123456789
```

---

## A2A Configuration

### Single-deployment (default)

All three agents (root, data, insights) are bundled in one Agent Engine deployment. ADK handles inter-agent routing internally — no extra configuration needed.

### Cross-deployment A2A (optional)

If you want to deploy the Data Agent independently (e.g., for reuse by other systems):

```bash
# Deploy data_agent standalone (modify deploy_agents.py to deploy data_agent only)
python -m deployment.deploy_agents --name education-data-agent

# Set the resource name
export DATA_AGENT_RESOURCE_NAME=projects/.../reasoningEngines/...
```

Then build a remote reference:
```python
from deployment.a2a_config import build_remote_agent
remote_data_agent = build_remote_agent("data_agent")
```

See [deployment/a2a_config.py](deployment/a2a_config.py) for the full A2A topology documentation.

---

## Running Tests

```bash
# All tests (no GCP required — BQ is mocked)
pytest tests/ -v

# Schema and SQL tests only
pytest tests/test_queries.py -v

# Agent and tool tests only
pytest tests/test_agents.py -v

# With coverage
pytest tests/ --cov=. --cov-report=term-missing
```

Expected output (30 tests):
```
tests/test_queries.py::TestBuildQuery::test_all_catalog_queries_build PASSED
tests/test_queries.py::TestSchema::test_csv_headers_match_schema[schools_master] PASSED
...
30 passed in 2.34s
```

---

## Test Queries and Expected Behaviour

### Query 1 — Grant prioritisation

**Input:**
> "Identify the five schools in Millbrook County with the highest rate of low-income students and the lowest per-pupil technology spending."

**Expected behaviour:**
- Routes to `data_agent` → calls `run_named_query("low_income_tech_gap", county="Millbrook", limit=5)`
- Returns schools 1001–1005 ranked by composite priority score
- Includes caveat that priority_score is a composite index, not an official metric
- Insights Agent adds recommendation to apply for Title I technology grants

**Expected top result:** Riverside Elementary (school_id 1001, 91.4% low-income, $112.50/pupil tech spending)

---

### Query 2 — Replication models

**Input:**
> "Find schools with high graduation rates despite below-average funding, to discover effective programme models."

**Expected behaviour:**
- Routes to `data_agent` → `run_named_query("high_grad_low_funding")`
- Returns schools 1018–1022 (all above state avg graduation rate, all below state avg funding)
- Insights Agent identifies Summit Ridge High (94.2% grad rate, $8,200 per-pupil) as top model
- Includes correlation note: "smaller class sizes co-occur with higher graduation rates in this subset"
- Explicitly does NOT claim causation

**Expected schools:** 1018, 1019, 1020, 1021, 1022

---

### Query 3 — STEM + small classes

**Input:**
> "Find schools with strong STEM programmes and low class sizes."

**Expected behaviour:**
- Routes to `data_agent` → `run_named_query("strong_stem_small_classes", min_stem_level=4, max_class_size=23)`
- Returns schools including 1017 (Elmwood STEM Academy, level 5, class size 19) and 1028 (Oakdale STEM High)
- Generates bar chart (STEM level) and scatter plot (class size vs math proficiency)

**Expected schools:** 1017, 1022, 1024, 1028, 1029

---

### Query 4 — Ambiguous query (clarification)

**Input:**
> "Which schools need help?"

**Expected behaviour:**
- Root agent identifies the query as too vague (no metric specified)
- Asks: "Could you be more specific? For example: schools needing help with funding, technology access, staffing, or academic performance?"
- Does NOT proceed to run a query without clarification

---

### Query 5 — County comparison

**Input:**
> "How do Millbrook County schools compare to Jefferson County schools on per-pupil funding?"

**Expected behaviour:**
- Routes to `data_agent` for data retrieval (`school_comparison` query with county filters)
- Routes to `insights_agent` for analysis
- Returns county_summary_chart (mean per-pupil funding by county)
- Reports the actual averages and the gap between counties

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `GOOGLE_CLOUD_PROJECT not set` | Copy `.env.example` to `.env` and fill in your project ID |
| `403 Permission denied on BigQuery` | Grant `roles/bigquery.dataViewer` and `roles/bigquery.jobUser` to your service account |
| `404 Dataset not found` | Run `python -m data.load_data` to create the dataset |
| `ModuleNotFoundError: google.adk` | Run `pip install -r requirements.txt` in your virtual environment |
| `kaleido` errors on chart export | Run `pip install kaleido` or install via conda: `conda install -c conda-forge python-kaleido` |
| Agent Engine deploy times out | First deploy takes 5–10 min; re-run if it times out — Agent Engine is idempotent |
| `RemoteAgent` not found | Ensure both `DATA_AGENT_RESOURCE_NAME` env vars are set for cross-deployment A2A |
| Plotly charts blank | Install a display backend: `pip install matplotlib` (used as fallback) |

---

## Security and Privacy Notes

- All BigQuery queries are **parameterized** — user input never interpolates into SQL strings.
- The system only reads data; no INSERT/UPDATE/DELETE is possible through any agent tool.
- Service account credentials should use the **principle of least privilege**: `bigquery.dataViewer` + `bigquery.jobUser` only.
- In production, use **Workload Identity** instead of service account key files.
- The dataset contains **no PII** — all records are school-level aggregates, not individual student data.
- Uploaded images/PDFs are sent to the Gemini API for extraction. Do not upload documents containing student PII.

---

## Architecture Overview

See [design_doc/architecture.md](design_doc/architecture.md) for the full design document covering:
- Agent architecture and responsibilities
- Data model and BigQuery schema
- A2A flow diagrams
- Security and privacy considerations
- Known limitations

---

## Contributing

1. Install dev dependencies: `pip install pytest pytest-mock ruff`
2. Run linter: `ruff check .`
3. Run tests: `pytest tests/ -v`
4. All tests must pass before submitting a PR.
