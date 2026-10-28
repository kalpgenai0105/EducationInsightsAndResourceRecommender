"""
Multimodal extraction tools for the Education Insights system.

Accepts uploaded images or PDFs (school budget tables, report cards, etc.)
and uses Gemini's vision capabilities to extract structured data that the
Data Agent can then query or compare against BigQuery results.

Typical workflow
----------------
1. User uploads a photo of a budget table or a scanned report card.
2. extract_data_from_image() sends it to Gemini with a schema-aware prompt.
3. The returned JSON is passed to the Data Agent for cross-referencing.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_MODEL_NAME = os.environ.get("AGENT_MODEL", "gemini-2.0-flash")

# Lazy-initialised Gemini client
_genai_client: genai.GenerativeModel | None = None


def _get_model() -> genai.GenerativeModel:
    global _genai_client
    if _genai_client is None:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        _genai_client = genai.GenerativeModel(_MODEL_NAME)
    return _genai_client


def _encode_image(image_path: str) -> tuple[str, str]:
    """Read an image file and return (base64_data, mime_type)."""
    path = pathlib.Path(image_path)
    suffix = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(suffix, "image/jpeg")
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode("utf-8")
    return data, mime_type


# ---------------------------------------------------------------------------
# Tool: extract structured data from an image
# ---------------------------------------------------------------------------

def extract_data_from_image(
    image_path: str,
    extraction_hint: str = "",
) -> str:
    """
    Extract structured data from an uploaded image (photo, scan, screenshot).

    Useful for:
    - Photos of school budget tables or funding documents
    - Scanned report cards or progress reports
    - Screenshots of district dashboards
    - Handwritten data entry forms

    Args:
        image_path: Absolute or relative path to the image file.
        extraction_hint: Optional description of what to extract, e.g.
                         'Extract the per-pupil spending and school name.'
                         If empty, a general extraction is attempted.

    Returns:
        JSON string with keys: extracted_fields, raw_text, confidence, notes.
    """
    model = _get_model()

    try:
        img_data, mime_type = _encode_image(image_path)
    except FileNotFoundError:
        return json.dumps({"error": f"Image file not found: {image_path}"})
    except Exception as exc:
        return json.dumps({"error": f"Could not read image: {exc}"})

    prompt = f"""
You are an education-data extraction assistant.

Analyse the provided image and extract all education-related data you can find.
Focus on: school names, district names, county, funding figures, test scores,
graduation rates, enrollment numbers, staffing ratios, and programme information.

{('Additional extraction goal: ' + extraction_hint) if extraction_hint else ''}

Return your response as valid JSON with this structure:
{{
  "extracted_fields": {{
    "school_name": "...",
    "district": "...",
    "county": "...",
    "per_pupil_funding_usd": null,
    "per_pupil_tech_spending_usd": null,
    "graduation_rate_pct": null,
    "math_proficiency_pct": null,
    "ela_proficiency_pct": null,
    "total_enrollment": null,
    "low_income_student_pct": null,
    "other_fields": {{}}
  }},
  "raw_text": "all text visible in the image",
  "confidence": "high|medium|low",
  "notes": "any caveats, illegible areas, or assumptions made"
}}

Use null for any field you cannot confidently read from the image.
Return only the JSON — no markdown fencing.
"""

    image_part = {"mime_type": mime_type, "data": img_data}

    try:
        response = model.generate_content([prompt, image_part])
        text = response.text.strip()
        # Strip optional markdown fences if the model adds them
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text
    except Exception as exc:
        return json.dumps({"error": f"Gemini extraction failed: {exc}"})


# ---------------------------------------------------------------------------
# Tool: extract data from a PDF (text-based)
# ---------------------------------------------------------------------------

def extract_data_from_pdf(
    pdf_path: str,
    page_range: str = "all",
    extraction_hint: str = "",
) -> str:
    """
    Extract structured education data from a PDF document.

    Best for: annual reports, district budgets, state accountability reports.
    Text-based PDFs are extracted directly; scanned PDFs fall back to image mode.

    Args:
        pdf_path: Path to the PDF file.
        page_range: 'all', a single page number (e.g. '3'), or a range ('2-5').
        extraction_hint: What to focus on.

    Returns:
        JSON string with keys: extracted_fields, tables, raw_text, page_count, notes.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        return json.dumps({"error": "pypdf is not installed. Run: pip install pypdf"})

    try:
        reader = PdfReader(pdf_path)
    except FileNotFoundError:
        return json.dumps({"error": f"PDF not found: {pdf_path}"})
    except Exception as exc:
        return json.dumps({"error": f"Could not open PDF: {exc}"})

    total_pages = len(reader.pages)

    # Parse page_range
    pages_to_read: list[int] = []
    if page_range == "all":
        pages_to_read = list(range(total_pages))
    elif "-" in str(page_range):
        start, end = page_range.split("-")
        pages_to_read = list(range(int(start) - 1, min(int(end), total_pages)))
    else:
        pages_to_read = [int(page_range) - 1]

    extracted_text = ""
    for page_num in pages_to_read:
        page = reader.pages[page_num]
        extracted_text += page.extract_text() or ""
        extracted_text += "\n\n"

    if not extracted_text.strip():
        return json.dumps({
            "error": "No text extracted — PDF may be image-based. "
                     "Save individual pages as images and use extract_data_from_image()."
        })

    # Use Gemini to structure the extracted text
    model = _get_model()
    prompt = f"""
You are an education-data extraction assistant.

Below is text extracted from a PDF document (pages {page_range} of {total_pages}).
Extract all education-related data and return it as JSON.

{('Focus on: ' + extraction_hint) if extraction_hint else ''}

Expected JSON structure:
{{
  "extracted_fields": {{
    "school_name": null,
    "district": null,
    "county": null,
    "fiscal_year": null,
    "per_pupil_funding_usd": null,
    "graduation_rate_pct": null,
    "total_enrollment": null,
    "other_fields": {{}}
  }},
  "tables": [
    {{"table_name": "...", "headers": [], "rows": []}}
  ],
  "raw_text": "...",
  "page_count": {total_pages},
  "notes": "..."
}}

Extracted text:
---
{extracted_text[:8000]}
---

Return only valid JSON.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text
    except Exception as exc:
        return json.dumps({"error": f"Gemini extraction failed: {exc}"})


# ---------------------------------------------------------------------------
# Tool: compare extracted data with BigQuery record
# ---------------------------------------------------------------------------

def compare_extracted_with_database(
    extracted_json: str,
    bq_school_json: str,
) -> str:
    """
    Compare fields extracted from an uploaded document with the corresponding
    BigQuery record and highlight discrepancies.

    Args:
        extracted_json: Output of extract_data_from_image() or extract_data_from_pdf().
        bq_school_json: Output of get_school_profile() from bigquery_tools.

    Returns:
        JSON string with keys: matches, discrepancies, missing_in_db, missing_in_doc.
    """
    try:
        extracted = json.loads(extracted_json)
        db_record  = json.loads(bq_school_json)
    except json.JSONDecodeError as exc:
        return json.dumps({"error": f"Could not parse JSON inputs: {exc}"})

    extracted_fields = extracted.get("extracted_fields", {})
    db_fields        = db_record.get("school", {})

    matches:         dict[str, Any] = {}
    discrepancies:   list[dict]     = []
    missing_in_db:   list[str]      = []
    missing_in_doc:  list[str]      = []

    for field, doc_val in extracted_fields.items():
        if field == "other_fields" or doc_val is None:
            continue
        db_val = db_fields.get(field)
        if db_val is None:
            missing_in_db.append(field)
        else:
            # Allow 5% tolerance for numeric fields
            try:
                if abs(float(doc_val) - float(db_val)) / (abs(float(db_val)) + 1e-9) < 0.05:
                    matches[field] = doc_val
                else:
                    discrepancies.append({
                        "field":    field,
                        "document": doc_val,
                        "database": db_val,
                    })
            except (TypeError, ValueError):
                if str(doc_val).strip().lower() == str(db_val).strip().lower():
                    matches[field] = doc_val
                else:
                    discrepancies.append({
                        "field":    field,
                        "document": doc_val,
                        "database": db_val,
                    })

    for field in db_fields:
        if field not in extracted_fields:
            missing_in_doc.append(field)

    return json.dumps({
        "matches":        matches,
        "discrepancies":  discrepancies,
        "missing_in_db":  missing_in_db,
        "missing_in_doc": missing_in_doc[:10],  # cap to avoid context overflow
        "summary": (
            f"{len(matches)} fields match, "
            f"{len(discrepancies)} discrepancies found, "
            f"{len(missing_in_db)} fields in document not in database."
        ),
    })
