"""
Unit tests for the data layer: SQL query builders, schema, and load_data validation.

These tests are offline — they do NOT require a live BigQuery connection.
They verify:
- build_query() produces syntactically correct SQL with the right parameters
- Schema field names match CSV headers
- Data-quality assertions (NULL graduation for non-HS, etc.)

Run with:  pytest tests/test_queries.py -v
"""

from __future__ import annotations

import csv
import pathlib

import pytest
from google.cloud import bigquery

from data.queries import QUERY_CATALOG, build_query
from data.schema import TABLE_CONFIG

DATA_DIR = pathlib.Path(__file__).parent.parent / "sample_data"


# ---------------------------------------------------------------------------
# Query builder tests
# ---------------------------------------------------------------------------

class TestBuildQuery:
    """Verify that build_query() returns well-formed SQL and parameters."""

    def _assert_valid(self, name: str, **kwargs):
        """Common assertion: SQL is non-empty, params is a list."""
        sql, params = build_query(name, project="test-project", dataset="test_ds", **kwargs)
        assert isinstance(sql, str)
        assert sql.strip().upper().startswith("SELECT")
        assert isinstance(params, list)
        for p in params:
            assert isinstance(p, (bigquery.ScalarQueryParameter, bigquery.ArrayQueryParameter))
        return sql, params

    def test_low_income_tech_gap_no_county(self):
        sql, params = self._assert_valid("low_income_tech_gap")
        assert "@limit" in sql
        assert not any(p.name == "county" for p in params)

    def test_low_income_tech_gap_with_county(self):
        sql, params = self._assert_valid("low_income_tech_gap", county="Millbrook", limit=5)
        assert "@county" in sql
        county_params = [p for p in params if p.name == "county"]
        assert len(county_params) == 1
        assert county_params[0].value == "Millbrook"

    def test_high_grad_low_funding_default(self):
        sql, params = self._assert_valid("high_grad_low_funding")
        # Default uses state_avg comparison, not a @grad_threshold param
        assert "@grad_threshold" not in sql

    def test_high_grad_low_funding_with_threshold(self):
        sql, params = self._assert_valid("high_grad_low_funding", grad_rate_threshold=90.0)
        assert "@grad_threshold" in sql
        threshold_param = next(p for p in params if p.name == "grad_threshold")
        assert threshold_param.value == pytest.approx(90.0)

    def test_strong_stem_small_classes(self):
        sql, params = self._assert_valid(
            "strong_stem_small_classes", min_stem_level=4, max_class_size=23.0
        )
        assert "@min_stem_level" in sql
        assert "@max_class_size" in sql

    def test_counselor_ratio_gap(self):
        sql, params = self._assert_valid("counselor_ratio_gap", county="Jefferson")
        assert "@county" in sql

    def test_school_comparison_with_ids(self):
        sql, params = self._assert_valid(
            "school_comparison", school_ids=[1001, 1002, 1018]
        )
        array_params = [p for p in params if isinstance(p, bigquery.ArrayQueryParameter)]
        assert len(array_params) == 1
        assert sorted(array_params[0].values) == [1001, 1002, 1018]

    def test_technology_equity(self):
        sql, params = self._assert_valid("technology_equity")
        assert "tech_equity_tier" in sql  # computed column is present

    def test_improving_schools(self):
        sql, params = self._assert_valid("improving_schools", limit=5)
        assert "year_over_year_improvement" in sql

    def test_unknown_query_raises(self):
        with pytest.raises(ValueError, match="Unknown query"):
            build_query("nonexistent_query", project="p", dataset="d")

    def test_all_catalog_queries_build(self):
        """Every name in QUERY_CATALOG must produce valid SQL."""
        for name in QUERY_CATALOG:
            sql, params = build_query(name, project="p", dataset="d")
            assert sql.strip(), f"Empty SQL for query '{name}'"

    def test_limit_parameter_present(self):
        """Every query with a limit parameter must include @limit in SQL."""
        queries_with_limit = [
            "low_income_tech_gap",
            "high_grad_low_funding",
            "strong_stem_small_classes",
            "counselor_ratio_gap",
            "technology_equity",
            "improving_schools",
        ]
        for name in queries_with_limit:
            sql, params = build_query(name, project="p", dataset="d", limit=5)
            assert "@limit" in sql, f"@limit missing in query '{name}'"

    def test_no_dml_in_any_query(self):
        """No pre-built query should contain DML keywords."""
        forbidden = ("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "TRUNCATE", "MERGE")
        for name in QUERY_CATALOG:
            sql, _ = build_query(name, project="p", dataset="d")
            upper = sql.upper()
            for kw in forbidden:
                assert kw not in upper, f"DML keyword '{kw}' found in query '{name}'"


# ---------------------------------------------------------------------------
# Schema / CSV consistency tests
# ---------------------------------------------------------------------------

class TestSchema:
    """Verify that CSV headers match the BigQuery schema definitions."""

    @pytest.mark.parametrize("table_name", list(TABLE_CONFIG.keys()))
    def test_csv_headers_match_schema(self, table_name: str):
        config = TABLE_CONFIG[table_name]
        csv_path = DATA_DIR / config["csv_file"]

        assert csv_path.exists(), f"CSV file missing: {csv_path}"

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            csv_headers = set(reader.fieldnames or [])

        schema_fields = {field.name for field in config["schema"]}
        missing = schema_fields - csv_headers
        assert not missing, (
            f"Table '{table_name}': schema fields missing from CSV: {sorted(missing)}"
        )

    @pytest.mark.parametrize("table_name", list(TABLE_CONFIG.keys()))
    def test_csv_has_30_rows(self, table_name: str):
        """Every CSV should have exactly 30 data rows (one per school)."""
        config = TABLE_CONFIG[table_name]
        csv_path = DATA_DIR / config["csv_file"]

        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        assert len(rows) == 30, (
            f"Table '{table_name}' has {len(rows)} rows; expected 30."
        )

    def test_school_ids_consistent_across_tables(self):
        """All five CSVs must have the same set of school_ids."""
        id_sets: dict[str, set[int]] = {}
        for table_name, config in TABLE_CONFIG.items():
            csv_path = DATA_DIR / config["csv_file"]
            with open(csv_path, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                id_sets[table_name] = {int(row["school_id"]) for row in reader}

        reference = id_sets["schools_master"]
        assert reference == set(range(1001, 1031)), "schools_master IDs are not 1001–1030"

        for table_name, ids in id_sets.items():
            assert ids == reference, (
                f"school_ids mismatch between schools_master and {table_name}: "
                f"extra={ids - reference}, missing={reference - ids}"
            )

    def test_graduation_rate_null_for_non_hs(self):
        """graduation_rate_pct should be empty for K-5, K-8, and 6-8 schools."""
        sm_path = DATA_DIR / "schools_master.csv"
        ap_path = DATA_DIR / "academic_performance.csv"

        with open(sm_path, newline="", encoding="utf-8") as fh:
            schools = {row["school_id"]: row["grade_levels"] for row in csv.DictReader(fh)}

        with open(ap_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                sid = row["school_id"]
                grades = schools.get(sid, "")
                grad = row.get("graduation_rate_pct", "").strip()
                if grades in ("K-5", "K-8", "6-8"):
                    assert grad == "", (
                        f"Expected empty graduation_rate_pct for school {sid} "
                        f"({grades}) but got '{grad}'"
                    )

    def test_stem_level_range(self):
        """stem_program_level must be in range 1–5."""
        csv_path = DATA_DIR / "programs_technology.csv"
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                level = int(row["stem_program_level"])
                assert 1 <= level <= 5, (
                    f"school_id {row['school_id']}: "
                    f"stem_program_level={level} is outside 1–5"
                )

    def test_low_income_pct_range(self):
        """low_income_student_pct must be between 0 and 100."""
        csv_path = DATA_DIR / "schools_master.csv"
        with open(csv_path, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                pct = float(row["low_income_student_pct"])
                assert 0.0 <= pct <= 100.0, (
                    f"school_id {row['school_id']}: "
                    f"low_income_student_pct={pct} out of range"
                )


# ---------------------------------------------------------------------------
# Known-value tests (golden data)
# Verify that notable records documented in sample_data/README.md are present.
# ---------------------------------------------------------------------------

class TestKnownValues:
    """Spot-check specific values against the documented expected records."""

    def _load_csv(self, filename: str) -> dict[str, dict]:
        path = DATA_DIR / filename
        with open(path, newline="", encoding="utf-8") as fh:
            return {row["school_id"]: row for row in csv.DictReader(fh)}

    def test_highest_low_income_schools_are_1001_to_1005(self):
        """Schools 1001–1005 should have the five highest low_income_student_pct values."""
        schools = self._load_csv("schools_master.csv")
        sorted_ids = sorted(
            schools.keys(),
            key=lambda sid: float(schools[sid]["low_income_student_pct"]),
            reverse=True,
        )
        top5 = set(sorted_ids[:5])
        expected = {"1001", "1002", "1003", "1004", "1005"}
        assert top5 == expected, f"Top-5 low-income schools: {top5}, expected {expected}"

    def test_strong_stem_schools_include_1017_and_1028(self):
        """Schools 1017 and 1028 (Elmwood STEM, Oakdale STEM High) should be Exemplary."""
        programs = self._load_csv("programs_technology.csv")
        assert programs["1017"]["stem_program_level"] == "5"
        assert programs["1028"]["stem_program_level"] == "5"

    def test_high_grad_low_funding_schools_include_1018_1019(self):
        """Schools 1018 and 1019 should have graduation rates above the state average."""
        performance = self._load_csv("academic_performance.csv")
        funding     = self._load_csv("funding_resources.csv")

        for sid in ("1018", "1019"):
            grad = float(performance[sid]["graduation_rate_pct"])
            state_avg = float(performance[sid]["state_avg_graduation_rate_pct"])
            per_pupil = float(funding[sid]["per_pupil_funding_usd"])
            state_avg_funding = float(funding[sid]["state_avg_per_pupil_funding_usd"])
            assert grad > state_avg, f"School {sid} grad rate not above state avg"
            assert per_pupil < state_avg_funding, f"School {sid} not underfunded"
