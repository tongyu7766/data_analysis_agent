"""Data Analysis Agent — CLI entry point.

The agent loop itself lives in agent_core.DataAnalysisAgent; this module
renders its event stream with rich terminal output.
"""

from __future__ import annotations

import os
import sys

import anthropic

import tools
from agent_core import INITIAL_PROMPT, DataAnalysisAgent
from display import (
    console,
    get_user_input,
    show_agent_message,
    show_banner,
    show_data_loaded,
    show_error,
    show_status,
    show_tool_call,
    show_tool_result,
)

SAMPLE_DATA = "sample_data.csv"


def run_turn(agent: DataAnalysisAgent, user_message: str) -> None:
    """Run one agentic turn, rendering each event as it happens."""
    events = agent.run_turn(user_message)
    status_message = "Thinking..."
    while True:
        # Advancing the generator is what performs the API call / tool run,
        # so the spinner wraps the fetch of the next event.
        with show_status(status_message):
            try:
                kind, payload = next(events)
            except StopIteration:
                return

        if kind == "thinking":
            status_message = "Thinking..."
        elif kind == "response":
            show_agent_message(payload)
        elif kind == "tool_call":
            show_tool_call(payload["name"], payload["input"])
            status_message = f"Running {payload['name']}..."
        elif kind == "tool_result":
            if payload["is_error"]:
                show_error(payload["result"])
            else:
                show_tool_result(payload["name"], payload["result"])
            status_message = "Thinking..."
        # "chart" events are already covered by the tool result output in the CLI


def main() -> None:
    show_banner()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        show_error("ANTHROPIC_API_KEY is not set. Set it and try again.")
        sys.exit(1)

    filepath = get_user_input_path()
    try:
        df = tools.load_dataframe(filepath)
    except Exception as exc:
        show_error(f"Failed to load '{filepath}': {exc}")
        sys.exit(1)
    show_data_loaded(filepath, len(df), df.shape[1])

    agent = DataAnalysisAgent(df, filepath)

    try:
        run_turn(agent, INITIAL_PROMPT)
    except anthropic.APIError as exc:
        show_error(f"API error: {exc}")

    # Interactive loop
    while True:
        try:
            user_input = get_user_input().strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        try:
            run_turn(agent, user_input)
        except anthropic.RateLimitError:
            show_error("Rate limited — wait a moment and try again.")
        except anthropic.APIConnectionError:
            show_error("Network error — check your connection and try again.")
        except anthropic.APIError as exc:
            show_error(f"API error: {exc}")
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")

    console.print(f"\n👋 Goodbye! Charts saved in {tools.OUTPUT_DIR}/")


def get_user_input_path() -> str:
    """Prompt for a CSV path; Enter falls back to the sample dataset."""
    from rich.prompt import Prompt

    path = Prompt.ask(
        "Enter CSV file path ([dim]press Enter for sample data[/dim])", default=SAMPLE_DATA
    ).strip()
    return path or SAMPLE_DATA


if __name__ == "__main__":
    main()
