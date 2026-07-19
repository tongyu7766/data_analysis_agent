"""Rich-based terminal display helpers for the Data Analysis Agent."""

from __future__ import annotations

import io
import sys
from contextlib import contextmanager

# On Windows consoles with a legacy codepage (e.g. GBK), emoji in panels would
# crash the writer — force UTF-8 with replacement so output degrades gracefully.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

import pandas as pd
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# Marker used by tools.py to flag CSV-encoded tabular sections in results
TABLE_MARKER = "[TABLE]"
TABLE_END_MARKER = "[/TABLE]"

MAX_RESULT_LINES = 30
MAX_TABLE_ROWS = 20

theme = Theme(
    {
        "agent": "cyan",
        "tool_call": "yellow",
        "tool_result": "green",
        "error": "red bold",
        "user": "bold white",
    }
)

console = Console(theme=theme)


def show_banner() -> None:
    """Print the startup banner."""
    banner = Text.assemble(
        ("📊 Data Analysis Agent v1.0\n", "bold cyan"),
        ("Natural language data analysis powered by AI", "dim"),
        justify="center",
    )
    console.print(Panel(banner, box=box.DOUBLE_EDGE, expand=False, padding=(1, 6)))


def show_agent_message(text: str) -> None:
    """Render the agent's response as markdown in a cyan panel."""
    console.print(
        Panel(
            Markdown(text),
            title="🤖 Agent",
            title_align="left",
            border_style="agent",
        )
    )


def show_tool_call(tool_name: str, tool_input: dict) -> None:
    """Print a compact line showing the tool being called."""
    args = ", ".join(f'{k}={v!r}' for k, v in tool_input.items())
    line = Text()
    line.append("🔧 Calling: ", style="tool_call")
    line.append(f"{tool_name}({args})", style="tool_call")
    console.print(line)


def _render_table(csv_text: str) -> Table:
    """Render a CSV block as a rich Table."""
    df = pd.read_csv(io.StringIO(csv_text))
    truncated = len(df) > MAX_TABLE_ROWS
    if truncated:
        df = df.head(MAX_TABLE_ROWS)

    table = Table(box=box.SIMPLE_HEAVY, header_style="bold", row_styles=["", "dim"])
    numeric_cols = set(df.select_dtypes("number").columns)
    for col in df.columns:
        table.add_column(str(col), justify="right" if col in numeric_cols else "left")
    for _, row in df.iterrows():
        table.add_row(
            *(
                f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)
                for v in row
            )
        )
    if truncated:
        table.caption = f"[dim]... showing first {MAX_TABLE_ROWS} rows[/dim]"
    return table


def show_tool_result(tool_name: str, result: str) -> None:
    """Show tool output in a green panel; render embedded CSV blocks as tables."""
    renderables = []
    remaining = result
    while TABLE_MARKER in remaining:
        before, _, rest = remaining.partition(TABLE_MARKER)
        csv_part, _, remaining = rest.partition(TABLE_END_MARKER)
        if before.strip():
            renderables.append(Text(_truncate(before.strip())))
        try:
            renderables.append(_render_table(csv_part.strip()))
        except Exception:
            renderables.append(Text(_truncate(csv_part.strip())))
    if remaining.strip():
        renderables.append(Text(_truncate(remaining.strip())))

    from rich.console import Group

    console.print(
        Panel(
            Group(*renderables) if renderables else Text("(empty result)"),
            title=f"📊 Tool Result: {tool_name}",
            title_align="left",
            border_style="tool_result",
        )
    )


def _truncate(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > MAX_RESULT_LINES:
        return "\n".join(lines[:MAX_RESULT_LINES]) + "\n[truncated]"
    return text


def show_data_loaded(filepath: str, rows: int, cols: int) -> None:
    """Show a success panel with file info."""
    body = Text.assemble(
        ("File:  ", "bold"),
        (f"{filepath}\n",),
        ("Shape: ", "bold"),
        (f"{rows:,} rows × {cols} columns",),
    )
    console.print(
        Panel(body, title="✅ Data Loaded", title_align="left", border_style="green", expand=False)
    )


def show_error(message: str) -> None:
    """Red-bordered panel for errors."""
    console.print(Panel(Text(message), title="❌ Error", title_align="left", border_style="error"))


def get_user_input() -> str:
    """Prompt the user for input."""
    return Prompt.ask("[user]You ▶[/user]")


@contextmanager
def show_status(message: str):
    """Spinner context manager for long-running operations (API calls, tools)."""
    with console.status(f"[dim]{message}[/dim]", spinner="dots"):
        yield
