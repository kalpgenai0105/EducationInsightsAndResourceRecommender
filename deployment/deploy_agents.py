"""
Vertex AI Agent Engine deployment script.

Packages the root_agent (with its sub-agents) and deploys it to Vertex AI
Agent Engine, where it is served as a managed, scalable endpoint.

Usage:
    python -m deployment.deploy_agents                # deploy / update
    python -m deployment.deploy_agents --list         # list deployed agents
    python -m deployment.deploy_agents --delete NAME  # delete a deployment
    python -m deployment.deploy_agents --test         # smoke-test after deploy

Prerequisites
-------------
1. GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION set in .env
2. BigQuery data loaded (python -m data.load_data)
3. Vertex AI API and Agent Engine API enabled in the project
4. Service account with roles:
   - roles/aiplatform.user
   - roles/bigquery.dataViewer
   - roles/bigquery.jobUser
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import vertexai
from dotenv import load_dotenv
from rich.console import Console
from vertexai import agent_engines

load_dotenv()
console = Console()

PROJECT  = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# Pinned requirement versions for the remote execution environment.
# These must match requirements.txt.  Only runtime deps are needed here
# (not pytest, ruff, etc.).
REMOTE_REQUIREMENTS = [
    "google-adk>=0.5.0",
    "google-cloud-bigquery>=3.10.0",
    "google-cloud-aiplatform>=1.60.0",
    "vertexai>=1.60.0",
    "google-auth>=2.20.0",
    "google-generativeai>=0.7.0",
    "pandas>=2.0.0",
    "db-dtypes>=1.1.0",
    "plotly>=5.15.0",
    "kaleido>=0.2.1",
    "pillow>=10.0.0",
    "pypdf>=3.17.0",
    "python-dotenv>=1.0.0",
    "pydantic>=2.5.0",
    "tenacity>=8.2.0",
    "numpy>=1.24.0",
]

# Environment variables to forward to the remote agent
REMOTE_ENV_VARS = {
    "GOOGLE_CLOUD_PROJECT":  PROJECT,
    "GOOGLE_CLOUD_LOCATION": LOCATION,
    "BIGQUERY_DATASET":      os.environ.get("BIGQUERY_DATASET", "education_insights"),
    "AGENT_MODEL":           os.environ.get("AGENT_MODEL", "gemini-2.0-flash"),
}


def deploy(display_name: str = "education-insights-agent") -> str:
    """
    Deploy or update the root_agent on Vertex AI Agent Engine.

    Returns the resource name of the deployed agent (persisted for A2A config).
    """
    if not PROJECT:
        console.print("[red]Error:[/red] GOOGLE_CLOUD_PROJECT is not set.")
        sys.exit(1)

    console.print(f"Initialising Vertex AI — project=[cyan]{PROJECT}[/cyan], "
                  f"location=[cyan]{LOCATION}[/cyan]")
    vertexai.init(project=PROJECT, location=LOCATION)

    # Import here so the module can be imported in tests without GCP credentials
    from agents import root_agent

    console.print("Wrapping root_agent in AdkApp…")
    app = agent_engines.AdkApp(
        agent=root_agent,
        enable_tracing=True,   # Cloud Trace integration for debugging
    )

    console.print(f"Deploying [bold]{display_name}[/bold] to Agent Engine…")
    console.print("  (this takes 3–8 minutes on first deploy)")

    remote_app = agent_engines.create(
        app,
        requirements=REMOTE_REQUIREMENTS,
        display_name=display_name,
        description=(
            "Multi-agent system for California school data analysis. "
            "Helps parents, educators, and officials identify needs, "
            "compare resources, and prioritise interventions."
        ),
        env_vars=REMOTE_ENV_VARS,
    )

    resource_name = remote_app.resource_name
    console.print(f"[green]Deployed successfully.[/green]")
    console.print(f"Resource name: [bold]{resource_name}[/bold]")
    console.print(
        "\nAdd this to your .env file:\n"
        f"AGENT_ENGINE_RESOURCE_NAME={resource_name}"
    )
    return resource_name


def list_deployments() -> None:
    """List all Agent Engine deployments in the project."""
    vertexai.init(project=PROJECT, location=LOCATION)
    console.print(f"Agent Engine deployments in {PROJECT}/{LOCATION}:")
    for app in agent_engines.list():
        console.print(
            f"  [cyan]{app.display_name}[/cyan]  "
            f"[dim]{app.resource_name}[/dim]"
        )


def delete_deployment(resource_name: str) -> None:
    """Delete a deployed Agent Engine application."""
    vertexai.init(project=PROJECT, location=LOCATION)
    app = agent_engines.get(resource_name)
    console.print(f"Deleting [red]{app.display_name}[/red]…")
    app.delete(force=True)
    console.print("[green]Deleted.[/green]")


def smoke_test(resource_name: str) -> None:
    """
    Send a test query to the deployed agent and print the response.
    Useful for verifying the deployment before going live.
    """
    vertexai.init(project=PROJECT, location=LOCATION)
    app = agent_engines.get(resource_name)

    session = app.create_session(user_id="smoke_test_user")

    test_query = (
        "Identify the five schools with the highest rate of low-income students "
        "and the lowest per-pupil technology spending."
    )
    console.print(f"Sending test query: [italic]{test_query}[/italic]")

    for event in app.stream_query(
        user_id="smoke_test_user",
        session_id=session["id"],
        message=test_query,
    ):
        if event.get("content"):
            parts = event["content"].get("parts", [])
            for part in parts:
                if "text" in part:
                    console.print(part["text"], end="")

    console.print("\n[green]Smoke test complete.[/green]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy Education Insights agents")
    parser.add_argument("--list",   action="store_true", help="List deployments")
    parser.add_argument("--delete", metavar="RESOURCE_NAME", help="Delete a deployment")
    parser.add_argument("--test",   metavar="RESOURCE_NAME", help="Smoke-test a deployment")
    parser.add_argument("--name",   default="education-insights-agent",
                        help="Display name for the deployment")
    args = parser.parse_args(argv)

    if not PROJECT:
        console.print("[red]GOOGLE_CLOUD_PROJECT not set.[/red]")
        return 1

    if args.list:
        list_deployments()
    elif args.delete:
        delete_deployment(args.delete)
    elif args.test:
        smoke_test(args.test)
    else:
        deploy(display_name=args.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
