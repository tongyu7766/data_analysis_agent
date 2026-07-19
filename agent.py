"""Data Analysis Agent — main entry point.

Implements a hand-written ReAct loop over the Anthropic Messages API:
user input -> Claude (with tools) -> execute tool_use blocks -> feed results
back -> repeat until Claude ends its turn with text.
"""

from __future__ import annotations

import os
import sys

import anthropic

import tools
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
from tool_schemas import TOOLS

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8192
SAMPLE_DATA = "sample_data.csv"

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


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool function; return (result_text, is_error)."""
    func = tools.TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True
    try:
        return func(**tool_input), False
    except Exception as exc:  # tool failures go back to Claude as error results
        return f"Error: {exc}", True


def run_turn(client: anthropic.Anthropic, messages: list) -> None:
    """Run one agentic turn: keep calling the API until Claude stops using tools."""
    while True:
        with show_status("Thinking..."):
            response = client.messages.create(
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
                messages=messages,
            )

        messages.append({"role": "assistant", "content": response.content})

        # Show any text Claude produced this round
        text = "\n\n".join(b.text for b in response.content if b.type == "text" and b.text.strip())
        if text:
            show_agent_message(text)

        if response.stop_reason == "refusal":
            show_error("The model declined to answer this request.")
            return
        if response.stop_reason != "tool_use":
            return

        # Execute every tool call and send all results back in one user message
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            show_tool_call(block.name, block.input)
            with show_status(f"Running {block.name}..."):
                result, is_error = execute_tool(block.name, block.input)
            if is_error:
                show_error(result)
            else:
                show_tool_result(block.name, result)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})


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

    client = anthropic.Anthropic()
    messages: list = [
        {
            "role": "user",
            "content": (
                "The dataset has been loaded. Please give me an overview of the data "
                "and suggest a few interesting questions I could explore."
            ),
        }
    ]

    try:
        run_turn(client, messages)
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

        messages.append({"role": "user", "content": user_input})
        try:
            run_turn(client, messages)
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
