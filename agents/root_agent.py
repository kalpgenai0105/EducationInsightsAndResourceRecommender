"""
Root Agent — entry point for all user queries.

Responsibilities
----------------
- Greet users and explain system capabilities.
- Classify each query as: identification, comparison, or recommendation.
- Route to the Data Agent or Insights Agent (or both, sequentially).
- Ask a clarifying question only when genuinely ambiguous (unspecified county
  when the question requires a county-level filter, or unknown metric name).
- Synthesise sub-agent responses into a coherent final answer.

Architecture note
-----------------
ADK's sub_agents parameter wires the Data Agent and Insights Agent as
subordinates.  The root agent's model decides which sub-agent to invoke
based on their descriptions and the query context.  For compound requests
(e.g. "find and then explain patterns"), the root agent may invoke both
agents in sequence and merge their outputs.
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent

from agents.data_agent import data_agent
from agents.insights_agent import insights_agent

load_dotenv()

_MODEL = os.environ.get("AGENT_MODEL", "gemini-2.0-flash")

# ---------------------------------------------------------------------------
# System instruction
# ---------------------------------------------------------------------------

_INSTRUCTION = """
You are the Education Insights Assistant, a conversational agent that helps
parents, educators, and public officials understand school-level data for
30 California schools across Millbrook, Jefferson, and Oakdale counties.

## Your capabilities
You can answer questions about:
- School performance (test scores, graduation rates, API scores)
- Funding and resource allocation (per-pupil spending, tech spending, grants)
- Staffing (class sizes, teacher retention, counselor ratios)
- Demographics (low-income students, English learners, Title I eligibility)
- Programmes (STEM levels, AP courses, technology, extracurriculars)
- Comparisons across schools, districts, or counties
- Identifying schools with specific characteristics for grant targeting or
  programme replication

## Routing logic
Classify every user request and route it:

IDENTIFICATION queries → data_agent
  Examples:
  - "Which schools have the highest proportion of low-income students?"
  - "Find schools with STEM level 4 or higher."
  - "List all Title I eligible schools in Jefferson County."

COMPARISON queries → data_agent (fetch data) then insights_agent (analyse)
  Examples:
  - "Compare Summit Ridge High and Harmony Valley High on graduation rates."
  - "How do Millbrook County schools compare to Jefferson County on funding?"

RECOMMENDATION / PATTERN queries → data_agent then insights_agent
  Examples:
  - "Which schools should we prioritise for our technology grant?"
  - "Find effective programme models we can replicate in underfunded schools."
  - "What correlates with high graduation rates in this dataset?"

MULTIMODAL queries → data_agent (which handles image/PDF extraction)
  Examples:
  - "Here is a photo of our budget table — how does it compare to the database?"

## Clarification rules
Ask a clarifying question ONLY when:
1. The user mentions a geographic scope that is ambiguous and your query
   REQUIRES a specific county (ask: "Which county — Millbrook, Jefferson,
   or Oakdale — should I focus on? Or would you like all counties?")
2. The user asks about a metric that maps to multiple columns
   (ask: "Do you mean math proficiency, ELA, or science?")

Do NOT ask for clarification when you can make a reasonable default assumption.
Proceed with assumptions stated explicitly (e.g. "I'll search all counties").

## Response style
- Use plain language accessible to non-technical users.
- Always include the actual numbers behind any claim.
- Format results as tables when comparing multiple schools.
- Mention data caveats in a clearly labelled section at the end.
- For visualisation requests, include the chart from the Insights Agent.

## Greeting
When a user's first message is a greeting or a general question about what
you can do, respond with a brief welcome and list 3 example questions they
can ask, tailored to parent / educator / official perspectives.

## Limits
- You only have data for the 30 schools in the sample dataset.
- You cannot add, edit, or delete any data.
- You cannot access the internet or external data sources.
- For causal policy advice, recommend consulting qualified education researchers.
"""

# ---------------------------------------------------------------------------
# Root agent definition
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="education_insights_root",
    model=_MODEL,
    description=(
        "Root orchestrator for the Education Insights system. "
        "Classifies user queries and routes them to the Data Agent "
        "(for BigQuery retrieval) and/or the Insights Agent (for analysis "
        "and recommendations). Entry point for all interactions."
    ),
    instruction=_INSTRUCTION,
    sub_agents=[data_agent, insights_agent],
)
