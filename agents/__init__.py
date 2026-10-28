"""
Agents package for the Education Insights & Resource Recommender system.

Exports the root_agent as the single entry point for all queries.
The ADK runner and Vertex AI Agent Engine both expect an 'agent' attribute
at the module level — the alias below satisfies that convention.
"""

from agents.root_agent import root_agent

# ADK convention: the deployable agent is exposed as `agent`
agent = root_agent

__all__ = ["root_agent", "agent"]
