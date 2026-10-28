"""
A2A (Agent-to-Agent) configuration for the Education Insights system.

Google ADK supports A2A communication natively when agents are deployed to
Vertex AI Agent Engine.  This module documents the A2A topology, provides
a helper to build A2AAgent references for remote agents, and shows how to
configure cross-agent calls.

A2A flow in this system
-----------------------
                         ┌─────────────────────────┐
  User / Client          │      Root Agent           │
  ─────────────  ──────► │  education_insights_root  │
                         │  (Vertex AI Agent Engine) │
                         └────────────┬──────────────┘
                                      │  A2A calls
                        ┌─────────────┴──────────────┐
                        ▼                            ▼
               ┌────────────────┐        ┌────────────────────┐
               │   Data Agent   │        │   Insights Agent   │
               │  data_agent    │        │  insights_agent    │
               └────────────────┘        └────────────────────┘

Within a single Agent Engine deployment, ADK handles the sub-agent routing
internally (no additional A2A URL configuration needed).

For cross-deployment A2A (e.g. the Data Agent deployed independently for
reuse by other systems), use the RemoteAgent pattern below.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT  = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# ---------------------------------------------------------------------------
# Agent card definitions
# Used for service discovery and for documenting the A2A surface area.
# ---------------------------------------------------------------------------

AGENT_CARDS: dict[str, dict[str, Any]] = {
    "root_agent": {
        "name":        "education_insights_root",
        "description": (
            "Root orchestrator. Accepts natural-language queries about CA school "
            "data and routes to the Data or Insights sub-agent."
        ),
        "capabilities": [
            "query_classification",
            "sub_agent_routing",
            "response_synthesis",
        ],
        "input_types":  ["text", "image", "pdf"],
        "output_types": ["text", "json", "chart_png_base64"],
        "endpoint_env": "AGENT_ENGINE_RESOURCE_NAME",
    },
    "data_agent": {
        "name":        "data_agent",
        "description": "Executes parameterized BigQuery queries; handles multimodal extraction.",
        "capabilities": [
            "bigquery_read",
            "schema_inspection",
            "image_extraction",
            "pdf_extraction",
        ],
        "input_types":  ["text", "json", "image", "pdf"],
        "output_types": ["json"],
        "endpoint_env": "DATA_AGENT_RESOURCE_NAME",   # set if deployed independently
    },
    "insights_agent": {
        "name":        "insights_agent",
        "description": "Analyses structured data; generates charts and recommendations.",
        "capabilities": [
            "pattern_analysis",
            "comparative_ranking",
            "chart_generation",
            "recommendation",
        ],
        "input_types":  ["json"],
        "output_types": ["text", "chart_png_base64"],
        "endpoint_env": "INSIGHTS_AGENT_RESOURCE_NAME",
    },
}


def get_agent_card(agent_name: str) -> dict[str, Any]:
    """Return the agent card for a named agent."""
    if agent_name not in AGENT_CARDS:
        raise ValueError(
            f"Unknown agent '{agent_name}'. "
            f"Available: {list(AGENT_CARDS.keys())}"
        )
    return AGENT_CARDS[agent_name]


def print_a2a_topology() -> None:
    """Print a human-readable summary of the A2A topology."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.rule("A2A Topology — Education Insights System")

    table = Table("Agent", "Capabilities", "Input Types", "Output Types")
    for name, card in AGENT_CARDS.items():
        table.add_row(
            f"[bold]{card['name']}[/bold]",
            ", ".join(card["capabilities"]),
            ", ".join(card["input_types"]),
            ", ".join(card["output_types"]),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# Remote agent factory
# Use this if agents are deployed to separate Agent Engine instances
# and need to call each other across deployments.
# ---------------------------------------------------------------------------

def build_remote_agent(agent_name: str):
    """
    Build an ADK RemoteAgent reference for an independently-deployed agent.

    This enables cross-deployment A2A: the root agent can call a Data Agent
    running in a different GCP project or region.

    Args:
        agent_name: One of the keys in AGENT_CARDS.

    Returns:
        google.adk.agents.RemoteAgent instance.

    Example:
        remote_data_agent = build_remote_agent("data_agent")
        root = Agent(name="root", ..., sub_agents=[remote_data_agent])
    """
    try:
        from google.adk.agents import RemoteAgent
        import vertexai
        from vertexai import agent_engines
    except ImportError as exc:
        raise ImportError(
            "google-adk and vertexai are required for RemoteAgent. "
            f"Original error: {exc}"
        ) from exc

    card = get_agent_card(agent_name)
    resource_name = os.environ.get(card["endpoint_env"], "")

    if not resource_name:
        raise EnvironmentError(
            f"Environment variable {card['endpoint_env']} is not set. "
            f"Deploy the {agent_name} first and set this variable."
        )

    vertexai.init(project=PROJECT, location=LOCATION)
    remote_engine = agent_engines.get(resource_name)

    return RemoteAgent(
        name=card["name"],
        description=card["description"],
        agent_engine=remote_engine,
    )


# ---------------------------------------------------------------------------
# A2A message schema
# Documents the JSON contract between agents for maintainability.
# ---------------------------------------------------------------------------

A2A_REQUEST_SCHEMA = {
    "type":       "object",
    "properties": {
        "query":        {"type": "string",  "description": "Natural language query"},
        "query_type":   {"type": "string",  "enum": ["identification", "comparison", "recommendation"]},
        "parameters":   {"type": "object",  "description": "Optional structured params (county, limit, etc.)"},
        "context":      {"type": "object",  "description": "Prior-turn context for multi-turn conversations"},
        "session_id":   {"type": "string"},
        "user_id":      {"type": "string"},
    },
    "required": ["query"],
}

A2A_RESPONSE_SCHEMA = {
    "type":       "object",
    "properties": {
        "answer":       {"type": "string",  "description": "Natural language answer"},
        "data":         {"type": "array",   "description": "Structured result rows"},
        "charts":       {"type": "object",  "description": "Map of chart_type → base64 PNG"},
        "caveats":      {"type": "array",   "items": {"type": "string"}},
        "agent_trace":  {"type": "array",   "description": "Which sub-agents were called"},
        "session_id":   {"type": "string"},
    },
    "required": ["answer"],
}


if __name__ == "__main__":
    print_a2a_topology()
