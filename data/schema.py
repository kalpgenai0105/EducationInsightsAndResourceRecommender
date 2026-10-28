"""
BigQuery table schema definitions for the Education Insights dataset.

Each table maps to one CSV in sample_data/.  All tables share school_id (INT64)
as the primary join key.  Schemas are expressed as lists of
google.cloud.bigquery.SchemaField so they can be used directly at table-creation
time and also surfaced to the Data Agent as context.
"""

from google.cloud import bigquery

# ---------------------------------------------------------------------------
# schools_master  – core school profiles with demographics
# ---------------------------------------------------------------------------
SCHOOLS_MASTER_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("school_id",                "INT64",   mode="REQUIRED", description="Unique school identifier (1001–1030)"),
    bigquery.SchemaField("school_name",              "STRING",  mode="REQUIRED", description="Full school name"),
    bigquery.SchemaField("district",                 "STRING",  mode="NULLABLE", description="School district name"),
    bigquery.SchemaField("county",                   "STRING",  mode="NULLABLE", description="County (Millbrook, Jefferson, Oakdale)"),
    bigquery.SchemaField("state",                    "STRING",  mode="NULLABLE", description="US state abbreviation"),
    bigquery.SchemaField("grade_levels",             "STRING",  mode="NULLABLE", description="Grade range served (e.g. K-5, 9-12)"),
    bigquery.SchemaField("school_type",              "STRING",  mode="NULLABLE", description="Public / Charter / Magnet"),
    bigquery.SchemaField("total_enrollment",         "INT64",   mode="NULLABLE", description="Total enrolled students"),
    bigquery.SchemaField("low_income_student_pct",   "FLOAT64", mode="NULLABLE", description="% students qualifying as low-income"),
    bigquery.SchemaField("free_reduced_lunch_pct",   "FLOAT64", mode="NULLABLE", description="% students on free/reduced-price lunch"),
    bigquery.SchemaField("english_learner_pct",      "FLOAT64", mode="NULLABLE", description="% English language learners"),
    bigquery.SchemaField("special_ed_pct",           "FLOAT64", mode="NULLABLE", description="% students with IEPs"),
    bigquery.SchemaField("chronic_absenteeism_pct",  "FLOAT64", mode="NULLABLE", description="% chronically absent (≥10% of days)"),
    bigquery.SchemaField("title_i_eligible",         "STRING",  mode="NULLABLE", description="Title I eligibility (Yes/No)"),
]

# ---------------------------------------------------------------------------
# academic_performance  – test scores, graduation, attendance
# ---------------------------------------------------------------------------
ACADEMIC_PERFORMANCE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("school_id",                        "INT64",   mode="REQUIRED"),
    bigquery.SchemaField("school_name",                      "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("math_proficiency_pct",             "FLOAT64", mode="NULLABLE", description="% students proficient in math"),
    bigquery.SchemaField("ela_proficiency_pct",              "FLOAT64", mode="NULLABLE", description="% students proficient in ELA"),
    bigquery.SchemaField("science_proficiency_pct",          "FLOAT64", mode="NULLABLE", description="% students proficient in science"),
    bigquery.SchemaField("state_avg_math_pct",               "FLOAT64", mode="NULLABLE", description="State average math proficiency"),
    bigquery.SchemaField("state_avg_ela_pct",                "FLOAT64", mode="NULLABLE", description="State average ELA proficiency"),
    bigquery.SchemaField("graduation_rate_pct",              "FLOAT64", mode="NULLABLE", description="4-year graduation rate (high schools only)"),
    bigquery.SchemaField("state_avg_graduation_rate_pct",    "FLOAT64", mode="NULLABLE", description="State average graduation rate"),
    bigquery.SchemaField("attendance_rate_pct",              "FLOAT64", mode="NULLABLE", description="Average daily attendance rate"),
    bigquery.SchemaField("suspension_rate_pct",              "FLOAT64", mode="NULLABLE", description="Suspension rate"),
    bigquery.SchemaField("college_readiness_pct",            "FLOAT64", mode="NULLABLE", description="% college-ready (high schools only)"),
    bigquery.SchemaField("api_score",                        "INT64",   mode="NULLABLE", description="Academic Performance Index score"),
    bigquery.SchemaField("school_rating",                    "INT64",   mode="NULLABLE", description="Overall rating 1–5"),
    bigquery.SchemaField("year_over_year_improvement",       "STRING",  mode="NULLABLE", description="Yes/No — improved vs prior year"),
]

# ---------------------------------------------------------------------------
# funding_resources  – per-pupil spending, budget breakdown
# ---------------------------------------------------------------------------
FUNDING_RESOURCES_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("school_id",                      "INT64",   mode="REQUIRED"),
    bigquery.SchemaField("school_name",                    "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("per_pupil_funding_usd",          "FLOAT64", mode="NULLABLE", description="Total per-pupil funding in USD"),
    bigquery.SchemaField("state_avg_per_pupil_funding_usd","FLOAT64", mode="NULLABLE", description="State average per-pupil funding"),
    bigquery.SchemaField("funding_gap_usd",                "FLOAT64", mode="NULLABLE", description="Gap vs state average (positive = underfunded)"),
    bigquery.SchemaField("local_tax_revenue_pct",          "FLOAT64", mode="NULLABLE", description="% of budget from local taxes"),
    bigquery.SchemaField("state_funding_pct",              "FLOAT64", mode="NULLABLE", description="% from state funds"),
    bigquery.SchemaField("federal_funding_pct",            "FLOAT64", mode="NULLABLE", description="% from federal funds"),
    bigquery.SchemaField("grant_funding_usd",              "FLOAT64", mode="NULLABLE", description="Total grant dollars received"),
    bigquery.SchemaField("per_pupil_tech_spending_usd",    "FLOAT64", mode="NULLABLE", description="Per-pupil technology spending"),
    bigquery.SchemaField("state_avg_tech_spending_usd",    "FLOAT64", mode="NULLABLE", description="State average tech spending per pupil"),
    bigquery.SchemaField("tech_spending_gap_usd",          "FLOAT64", mode="NULLABLE", description="Tech spending gap vs state average"),
    bigquery.SchemaField("library_budget_usd",             "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("counseling_budget_usd",          "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("extracurricular_budget_usd",     "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("maintenance_budget_usd",         "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("title_i_funds_usd",              "FLOAT64", mode="NULLABLE", description="Title I allocation (0 if not eligible)"),
]

# ---------------------------------------------------------------------------
# staffing  – teacher metrics, class sizes, support staff ratios
# ---------------------------------------------------------------------------
STAFFING_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("school_id",                    "INT64",   mode="REQUIRED"),
    bigquery.SchemaField("school_name",                  "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("total_teachers",               "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("avg_teacher_experience_years", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("teacher_retention_rate_pct",   "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("teacher_certification_rate_pct","FLOAT64",mode="NULLABLE"),
    bigquery.SchemaField("national_board_certified_pct", "FLOAT64", mode="NULLABLE", description="% teachers with National Board Certification"),
    bigquery.SchemaField("avg_class_size",               "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("student_to_teacher_ratio",     "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("student_to_counselor_ratio",   "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("student_to_librarian_ratio",   "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("student_to_admin_ratio",       "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("principal_tenure_years",       "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("instructional_coaches",        "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("stem_certified_teachers",      "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("special_ed_teachers",          "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("ell_specialists",              "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("teacher_vacancies",            "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("substitute_fill_rate_pct",     "FLOAT64", mode="NULLABLE"),
]

# ---------------------------------------------------------------------------
# programs_technology  – STEM levels, AP courses, device ratios, broadband
# ---------------------------------------------------------------------------
PROGRAMS_TECHNOLOGY_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("school_id",                  "INT64",   mode="REQUIRED"),
    bigquery.SchemaField("school_name",                "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("stem_program",               "STRING",  mode="NULLABLE", description="Text label (Basic/Moderate/Good/Strong/Exemplary)"),
    bigquery.SchemaField("stem_program_level",         "INT64",   mode="NULLABLE", description="Numeric level 1–5"),
    bigquery.SchemaField("robotics_club",              "STRING",  mode="NULLABLE", description="Yes/No"),
    bigquery.SchemaField("coding_classes",             "STRING",  mode="NULLABLE", description="Yes/No"),
    bigquery.SchemaField("advanced_placement_courses", "INT64",   mode="NULLABLE", description="Number of AP courses offered"),
    bigquery.SchemaField("dual_enrollment_courses",    "INT64",   mode="NULLABLE", description="Number of dual-enrollment courses"),
    bigquery.SchemaField("career_tech_education",      "STRING",  mode="NULLABLE", description="Yes/No"),
    bigquery.SchemaField("arts_program",               "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("music_program",              "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("sports_programs",            "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("after_school_program",       "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("mentorship_program",         "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("tutoring_program",           "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("community_partnerships",     "INT64",   mode="NULLABLE", description="Number of active community partnerships"),
    bigquery.SchemaField("restorative_justice",        "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("gifted_program",             "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("ell_support_program",        "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("avg_device_age_years",       "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("student_to_device_ratio",    "FLOAT64", mode="NULLABLE", description="Students per device (<1 = more devices than students)"),
    bigquery.SchemaField("broadband_mbps",             "FLOAT64", mode="NULLABLE", description="Internet bandwidth in Mbps"),
    bigquery.SchemaField("lms_platform",               "STRING",  mode="NULLABLE", description="Learning management system (Canvas/Google Classroom/Schoology)"),
    bigquery.SchemaField("devices_per_classroom",      "INT64",   mode="NULLABLE"),
    bigquery.SchemaField("smartboards_pct",            "FLOAT64", mode="NULLABLE", description="% classrooms with smartboards"),
    bigquery.SchemaField("computer_lab",               "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("makerspaces",                "STRING",  mode="NULLABLE"),
    bigquery.SchemaField("avg_tech_uptime_pct",        "FLOAT64", mode="NULLABLE", description="Average technology uptime %"),
]

# ---------------------------------------------------------------------------
# Convenience mapping: table name → schema + CSV filename
# ---------------------------------------------------------------------------
TABLE_CONFIG: dict[str, dict] = {
    "schools_master": {
        "schema": SCHOOLS_MASTER_SCHEMA,
        "csv_file": "schools_master.csv",
        "description": "Core school profiles with enrollment and demographic data",
    },
    "academic_performance": {
        "schema": ACADEMIC_PERFORMANCE_SCHEMA,
        "csv_file": "academic_performance.csv",
        "description": "Test scores, graduation rates, and school ratings",
    },
    "funding_resources": {
        "schema": FUNDING_RESOURCES_SCHEMA,
        "csv_file": "funding_resources.csv",
        "description": "Per-pupil funding, spending breakdown, and funding gaps",
    },
    "staffing": {
        "schema": STAFFING_SCHEMA,
        "csv_file": "staffing.csv",
        "description": "Teacher metrics, class sizes, and support staff ratios",
    },
    "programs_technology": {
        "schema": PROGRAMS_TECHNOLOGY_SCHEMA,
        "csv_file": "programs_technology.csv",
        "description": "STEM programs, AP courses, devices, and broadband",
    },
}

# Human-readable schema summary returned to the Data Agent as context
SCHEMA_SUMMARY = """
Education Insights BigQuery Dataset — Table Overview
=====================================================
Join key: school_id (INT64), values 1001–1030, 30 schools across 3 CA counties
          (Millbrook, Jefferson, Oakdale)

schools_master
  school_id, school_name, district, county, state, grade_levels, school_type,
  total_enrollment, low_income_student_pct, free_reduced_lunch_pct,
  english_learner_pct, special_ed_pct, chronic_absenteeism_pct, title_i_eligible

academic_performance
  school_id, math/ela/science_proficiency_pct, state_avg_math/ela_pct,
  graduation_rate_pct (high schools only), state_avg_graduation_rate_pct,
  attendance_rate_pct, suspension_rate_pct, college_readiness_pct (HS only),
  api_score, school_rating (1–5), year_over_year_improvement

funding_resources
  school_id, per_pupil_funding_usd, state_avg_per_pupil_funding_usd,
  funding_gap_usd, local_tax_revenue_pct, state_funding_pct, federal_funding_pct,
  grant_funding_usd, per_pupil_tech_spending_usd, state_avg_tech_spending_usd,
  tech_spending_gap_usd, library/counseling/extracurricular/maintenance_budget_usd,
  title_i_funds_usd

staffing
  school_id, total_teachers, avg_teacher_experience_years,
  teacher_retention_rate_pct, teacher_certification_rate_pct,
  national_board_certified_pct, avg_class_size, student_to_teacher_ratio,
  student_to_counselor_ratio, student_to_librarian_ratio, student_to_admin_ratio,
  principal_tenure_years, instructional_coaches, stem_certified_teachers,
  special_ed_teachers, ell_specialists, teacher_vacancies, substitute_fill_rate_pct

programs_technology
  school_id, stem_program (text), stem_program_level (1–5), robotics_club,
  coding_classes, advanced_placement_courses, dual_enrollment_courses,
  career_tech_education, arts/music/sports_programs, after_school_program,
  mentorship_program, tutoring_program, community_partnerships,
  restorative_justice, gifted_program, ell_support_program,
  avg_device_age_years, student_to_device_ratio, broadband_mbps, lms_platform,
  devices_per_classroom, smartboards_pct, computer_lab, makerspaces,
  avg_tech_uptime_pct

Data quality notes
------------------
- graduation_rate_pct and college_readiness_pct are NULL for non-high-school rows
- title_i_funds_usd is 0 (not NULL) when a school is not Title I eligible
- stem_program_level 1=Basic, 2=Moderate, 3=Good, 4=Strong, 5=Exemplary
- Coordinates / latitude-longitude are NOT present; map views require an
  external geocoding step using school_name + district + county + state
"""
