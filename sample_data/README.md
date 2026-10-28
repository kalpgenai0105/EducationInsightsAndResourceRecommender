# Education Insights Sample Data

Sample dataset for the **Education Insights & Resource Recommender** capstone project.
30 schools across 3 counties (Millbrook, Jefferson, Oakdale) in California.

## Files

| File | Description | Key Columns |
|------|-------------|-------------|
| `schools_master.csv` | Core school profiles | enrollment, demographics, Title I eligibility |
| `funding_resources.csv` | Per-pupil funding, spending breakdown | per_pupil_funding_usd, per_pupil_tech_spending_usd, funding_gap_usd |
| `academic_performance.csv` | Test scores, graduation rates | math/ela/science proficiency, graduation_rate_pct, api_score |
| `staffing.csv` | Teachers, class sizes, student-to-staff ratios | avg_class_size, student_to_counselor_ratio, teacher_retention_rate_pct |
| `programs_technology.csv` | STEM programs, AP courses, devices, broadband | stem_program_level (1–5), student_to_device_ratio, broadband_mbps |

## Join Key
All files share `school_id` (1001–1030) as the primary key.

## Sample Agent Queries Supported

1. **"Top 5 schools with highest low-income students AND lowest tech spending"**
   - Join `schools_master` + `funding_resources`
   - Filter: `low_income_student_pct` (high) + `per_pupil_tech_spending_usd` (low)

2. **"High graduation rate despite below-average funding"**
   - Join `academic_performance` + `funding_resources`
   - Filter: `graduation_rate_pct > state_avg` AND `per_pupil_funding_usd < state_avg`

3. **"Strong STEM programs with low class sizes"**
   - Join `programs_technology` + `staffing`
   - Filter: `stem_program_level >= 4` AND `avg_class_size <= 23`

## Notable Records for Testing

| Query | School IDs |
|-------|------------|
| Highest low-income + lowest tech spending | 1001, 1002, 1003, 1004, 1005 |
| High grad rate, low funding (replication models) | 1018, 1019, 1020, 1021, 1022 |
| Strong STEM + small classes | 1017, 1028, 1022, 1029, 1018 |
