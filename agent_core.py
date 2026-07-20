"""Core agent logic shared by the CLI (agent.py) and the Streamlit app (app.py).

The ReAct loop lives in DataAnalysisAgent.run_turn(), a generator that yields
UI-agnostic events so each frontend can render progress in its own way.
"""

from __future__ import annotations

import os
from typing import Any, Generator

import anthropic
import pandas as pd

import tools
from tool_schemas import TOOLS

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192

SYSTEM_PROMPT = """You are a professional data analysis assistant. A dataset has been loaded and you have access to various tools to analyze it.

Your workflow:
1. Understand the user's analysis goal
2. Choose the right tool(s) to execute the analysis
3. Interpret the results in clear, accessible language with specific numbers
4. Proactively suggest follow-up analyses or visualizations when relevant

Guidelines:
- Start with data_overview to understand the full picture before diving deep
- Be specific in your insights — cite actual values, percentages, and trends
- When you spot anomalies or interesting patterns, point them out proactively
- When a visualization would help, call create_visualization without being asked
- If a question requires multiple tools, chain them in sequence
- Respond in English by default, or match the user's language
"""

INITIAL_PROMPT = (
    "The dataset has been loaded. Please give me an overview of the data "
    "and suggest a few interesting questions I could explore."
)

# Events yielded by run_turn():
#   ("thinking", None)                          about to call the API
#   ("tool_call", {"name", "input"})            agent is calling a tool
#   ("tool_result", {"name", "result", "is_error"})
#   ("chart", filepath)                         create_visualization saved a PNG
#   ("response", text)                          agent text (may occur mid-turn and at the end)
Event = tuple[str, Any]

CHART_MARKER = "Chart saved: "


def resolve_api_key() -> str | None:
    """Resolve the Anthropic API key.

    Checks st.secrets first (Streamlit Cloud's secrets manager), then falls
    back to the ANTHROPIC_API_KEY environment variable. Streamlit is an
    optional dependency here — this works unchanged when only the CLI
    (agent.py) is installed and st.secrets isn't available.
    """
    try:
        import streamlit as st

        key = st.secrets.get("ANTHROPIC_API_KEY")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool function; return (result_text, is_error)."""
    func = tools.TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True
    try:
        return func(**tool_input), False
    except Exception as exc:  # tool failures go back to Claude as error results
        return f"Error: {exc}", True


def _extract_chart_path(result: str) -> str | None:
    for line in result.splitlines():
        if line.startswith(CHART_MARKER):
            return line[len(CHART_MARKER):].strip()
    return None


class DataAnalysisAgent:
    """Holds the conversation and drives the tool-use loop for one dataset."""

    def __init__(self, df: pd.DataFrame, source_name: str = "dataset"):
        self.df = df
        self.source_name = source_name
        self.messages: list = []
        self.client = anthropic.Anthropic(api_key=resolve_api_key())
        tools.set_dataframe(df, source_name)

    def run_turn(self, user_message: str) -> Generator[Event, None, None]:
        """Send a message and yield events as the agentic turn progresses."""
        # tools.py holds the dataset as module state; re-install ours in case
        # another agent instance (e.g. a different Streamlit session) swapped it.
        tools.set_dataframe(self.df, self.source_name)
        self.messages.append({"role": "user", "content": user_message})

        while True:
            yield ("thinking", None)
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=self.messages,
            )

            self.messages.append({"role": "assistant", "content": response.content})

            text = "\n\n".join(
                b.text for b in response.content if b.type == "text" and b.text.strip()
            )
            if response.stop_reason == "refusal":
                yield ("response", text or "The model declined to answer this request.")
                return
            if text:
                yield ("response", text)
            if response.stop_reason != "tool_use":
                return

            # Execute every tool call and send all results back in one user message
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                yield ("tool_call", {"name": block.name, "input": block.input})
                result, is_error = execute_tool(block.name, block.input)
                yield (
                    "tool_result",
                    {"name": block.name, "result": result, "is_error": is_error},
                )
                if not is_error and block.name == "create_visualization":
                    chart_path = _extract_chart_path(result)
                    if chart_path:
                        yield ("chart", chart_path)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                        "is_error": is_error,
                    }
                )
            self.messages.append({"role": "user", "content": tool_results})
