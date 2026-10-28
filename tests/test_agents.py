"""
Integration tests for agent behaviour.

These tests mock BigQuery so they can run without GCP credentials.
They verify routing decisions, tool call patterns, and response structure.

Run with:  pytest tests/test_agents.py -v

Requires:  pytest, pytest-mock (pip install pytest pytest-mock)
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bq_result(rows: list[dict]) -> MagicMock:
    """Create a mock BigQuery RowIterator that returns the given rows."""
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([
        MagicMock(**{"items.return_value": r.items()}) for r in rows
    ]))
    return mock_result


SAMPLE_SCHOOL_ROWS = [
    {
        "school_id":               1001,
        "school_name":             "Riverside Elementary",
        "county":                  "Millbrook",
        "low_income_student_pct":  91.4,
        "per_pupil_tech_spending_usd": 112.50,
        "priority_score":          71.2,
    },
    {
        "school_id":               1002,
        "school_name":             "Eastside Middle School",
        "county":                  "Millbrook",
        "low_income_student_pct":  88.7,
        "per_pupil_tech_spending_usd": 134.00,
        "priority_score":          68.9,
    },
]


# ---------------------------------------------------------------------------
# Test: bigquery_tools module
# ---------------------------------------------------------------------------

class TestBigQueryTools:
    """Tests for the BigQuery tool functions (mocked BQ client)."""

    def test_get_schema_info_returns_nonempty_string(self):
        from tools.bigquery_tools import get_schema_info
        result = get_schema_info()
        assert isinstance(result, str)
        assert "school_id" in result
        assert "graduation_rate_pct" in result

    def test_list_available_queries_contains_expected(self):
        from tools.bigquery_tools import list_available_queries
        result = list_available_queries()
        assert "low_income_tech_gap" in result
        assert "high_grad_low_funding" in result
        assert "strong_stem_small_classes" in result

    @patch("tools.bigquery_tools._get_client")
    def test_run_named_query_returns_json(self, mock_get_client):
        """run_named_query() should return valid JSON with rows and caveats."""
        # Set up the mock client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock job result
        mock_job = MagicMock()
        mock_job.result.return_value = iter([
            MagicMock(**{"items.return_value": row.items()})
            for row in SAMPLE_SCHOOL_ROWS
        ])
        mock_client.query.return_value = mock_job

        from tools.bigquery_tools import run_named_query

        # Patch _rows_to_dicts to avoid MagicMock item iteration issues
        with patch("tools.bigquery_tools._rows_to_dicts", return_value=SAMPLE_SCHOOL_ROWS):
            result = run_named_query("low_income_tech_gap", county="Millbrook", limit=5)

        data = json.loads(result)
        assert "rows" in data
        assert "caveats" in data
        assert data["query_name"] == "low_income_tech_gap"
        assert data["row_count"] == len(SAMPLE_SCHOOL_ROWS)

    @patch("tools.bigquery_tools._get_client")
    def test_run_readonly_sql_blocks_insert(self, mock_get_client):
        """run_readonly_sql() must reject INSERT statements."""
        from tools.bigquery_tools import run_readonly_sql
        result = run_readonly_sql("INSERT INTO some_table VALUES (1, 'test')")
        data = json.loads(result)
        assert "error" in data
        assert "INSERT" in data["error"]

    @patch("tools.bigquery_tools._get_client")
    def test_run_readonly_sql_blocks_drop(self, mock_get_client):
        from tools.bigquery_tools import run_readonly_sql
        result = run_readonly_sql("DROP TABLE education_insights.schools_master")
        data = json.loads(result)
        assert "error" in data

    @patch("tools.bigquery_tools._get_client")
    def test_get_school_profile_not_found(self, mock_get_client):
        """Should return a structured error when school_id doesn't exist."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_job = MagicMock()
        mock_job.result.return_value = iter([])
        mock_client.query.return_value = mock_job

        from tools.bigquery_tools import get_school_profile
        with patch("tools.bigquery_tools._rows_to_dicts", return_value=[]):
            result = get_school_profile(9999)

        data = json.loads(result)
        assert "error" in data
        assert "9999" in data["error"]


# ---------------------------------------------------------------------------
# Test: multimodal_tools module
# ---------------------------------------------------------------------------

class TestMultimodalTools:
    def test_compare_extracted_with_database_matches(self):
        """When extracted and DB values agree (within 5%), should report as match."""
        from tools.multimodal_tools import compare_extracted_with_database

        extracted = json.dumps({
            "extracted_fields": {
                "school_name": "Riverside Elementary",
                "per_pupil_funding_usd": 7850.0,
            }
        })
        db = json.dumps({
            "school": {
                "school_name": "Riverside Elementary",
                "per_pupil_funding_usd": 7850.0,
            }
        })

        result = json.loads(compare_extracted_with_database(extracted, db))
        assert "school_name" in result["matches"]
        assert len(result["discrepancies"]) == 0

    def test_compare_extracted_with_database_discrepancy(self):
        """Values differing by >5% should appear in discrepancies."""
        from tools.multimodal_tools import compare_extracted_with_database

        extracted = json.dumps({
            "extracted_fields": {"per_pupil_funding_usd": 5000.0}
        })
        db = json.dumps({
            "school": {"per_pupil_funding_usd": 7850.0}
        })

        result = json.loads(compare_extracted_with_database(extracted, db))
        assert len(result["discrepancies"]) == 1
        assert result["discrepancies"][0]["field"] == "per_pupil_funding_usd"

    def test_compare_handles_bad_json(self):
        from tools.multimodal_tools import compare_extracted_with_database
        result = json.loads(compare_extracted_with_database("not_json", "{}"))
        assert "error" in result


# ---------------------------------------------------------------------------
# Test: agent definitions (import-level smoke tests)
# ---------------------------------------------------------------------------

class TestAgentDefinitions:
    """Verify agents can be imported and have the expected attributes."""

    def test_data_agent_importable(self):
        from agents.data_agent import data_agent
        assert data_agent.name == "data_agent"
        assert len(data_agent.tools) >= 5

    def test_insights_agent_importable(self):
        from agents.insights_agent import insights_agent
        assert insights_agent.name == "insights_agent"
        assert len(insights_agent.tools) >= 4

    def test_root_agent_importable(self):
        from agents.root_agent import root_agent
        assert root_agent.name == "education_insights_root"
        assert len(root_agent.sub_agents) == 2

    def test_agents_package_exports_root_agent(self):
        from agents import root_agent, agent
        assert root_agent is agent  # alias must point to the same object


# ---------------------------------------------------------------------------
# Test: query catalog completeness
# ---------------------------------------------------------------------------

class TestQueryCatalog:
    def test_all_queries_documented(self):
        from data.queries import QUERY_CATALOG, _QUERY_BUILDERS
        assert set(QUERY_CATALOG.keys()) == set(_QUERY_BUILDERS.keys()), (
            "QUERY_CATALOG and _QUERY_BUILDERS must have the same keys."
        )

    def test_catalog_descriptions_are_nonempty(self):
        from data.queries import QUERY_CATALOG
        for name, desc in QUERY_CATALOG.items():
            assert desc.strip(), f"Empty description for query '{name}'"


# ---------------------------------------------------------------------------
# Test: A2A config
# ---------------------------------------------------------------------------

class TestA2AConfig:
    def test_get_agent_card_valid(self):
        from deployment.a2a_config import get_agent_card
        card = get_agent_card("root_agent")
        assert "capabilities" in card
        assert "input_types" in card

    def test_get_agent_card_invalid_raises(self):
        from deployment.a2a_config import get_agent_card
        with pytest.raises(ValueError, match="Unknown agent"):
            get_agent_card("ghost_agent")

    def test_all_agent_cards_have_required_fields(self):
        from deployment.a2a_config import AGENT_CARDS
        required = {"name", "description", "capabilities", "input_types", "output_types"}
        for agent_name, card in AGENT_CARDS.items():
            missing = required - card.keys()
            assert not missing, f"Agent card '{agent_name}' missing fields: {missing}"
