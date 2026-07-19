"""Data Analysis Agent — Streamlit web frontend.

Wraps agent_core.DataAnalysisAgent in a chat UI: upload a CSV (or use the
sample data), get an automatic overview, then ask questions in natural
language. Tool calls render in expanders; charts render inline.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import io
import os

import anthropic
import pandas as pd
import streamlit as st

import tools
from agent_core import INITIAL_PROMPT, DataAnalysisAgent
from display import TABLE_END_MARKER, TABLE_MARKER

SAMPLE_DATA = "sample_data.csv"

st.set_page_config(
    page_title="Data Analysis Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* Tool-call expanders stand out slightly from regular chat content */
    div[data-testid="stChatMessage"] details {
        background-color: rgba(79, 143, 247, 0.07);
        border: 1px solid rgba(79, 143, 247, 0.25);
        border-radius: 8px;
    }
    /* Comfortable chat message padding */
    div[data-testid="stChatMessage"] {
        padding: 0.75rem 1rem;
    }
    /* Card-like stats panel in the sidebar */
    section[data-testid="stSidebar"] div[data-testid="stMetric"] {
        background-color: rgba(79, 143, 247, 0.08);
        border: 1px solid rgba(79, 143, 247, 0.2);
        border-radius: 8px;
        padding: 0.5rem 0.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("Please set ANTHROPIC_API_KEY environment variable")
    st.stop()

# ---------------------------------------------------------------- state

state_defaults = {
    "df": None,             # loaded DataFrame
    "filename": None,       # uploaded file name
    "messages": [],         # chat history (user text / assistant event lists)
    "agent": None,          # DataAnalysisAgent instance
    "pending_prompt": None, # prompt queued to run on this rerun (initial overview)
    "loaded_file_key": None,  # (name, size) of the processed upload
}
for key, default in state_defaults.items():
    st.session_state.setdefault(key, default)


def load_data(df: pd.DataFrame, filename: str) -> None:
    """Install a new dataset, reset the chat, and queue the initial overview."""
    st.session_state.df = df
    st.session_state.filename = filename
    st.session_state.messages = []
    st.session_state.agent = DataAnalysisAgent(df, filename)
    st.session_state.pending_prompt = INITIAL_PROMPT


# ---------------------------------------------------------------- rendering


def render_tool_result(result: str, is_error: bool) -> None:
    """Render tool output; [TABLE]...[/TABLE] CSV blocks become dataframes."""
    if is_error:
        st.error(result)
        return
    remaining = result
    while TABLE_MARKER in remaining:
        before, _, rest = remaining.partition(TABLE_MARKER)
        csv_part, _, remaining = rest.partition(TABLE_END_MARKER)
        if before.strip():
            st.text(before.strip())
        try:
            st.dataframe(pd.read_csv(io.StringIO(csv_part.strip())), width="stretch")
        except Exception:
            st.text(csv_part.strip())
    if remaining.strip():
        st.text(remaining.strip())


def render_event(event: dict, key: str) -> None:
    """Render one stored assistant event (text, tool call, or chart)."""
    if event["type"] == "text":
        st.markdown(event["text"])
    elif event["type"] == "tool":
        with st.expander(f"🔧 {event['name']}"):
            if event["input"]:
                st.caption("Input")
                st.json(event["input"])
            st.caption("Result")
            render_tool_result(event["result"], event["is_error"])
    elif event["type"] == "chart":
        st.image(event["data"])
        st.download_button(
            "Download Chart",
            data=event["data"],
            file_name=os.path.basename(event["path"]),
            mime="image/png",
            key=f"dl_{key}",
        )


def run_agent_turn(prompt: str) -> None:
    """Run one agent turn inside an assistant chat message, rendering live."""
    agent: DataAnalysisAgent = st.session_state.agent
    events: list[dict] = []
    msg_index = len(st.session_state.messages)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            pending_call: dict | None = None
            try:
                for kind, payload in agent.run_turn(prompt):
                    if kind == "tool_call":
                        pending_call = payload
                    elif kind == "tool_result":
                        event = {
                            "type": "tool",
                            "name": payload["name"],
                            "input": pending_call["input"] if pending_call else {},
                            "result": payload["result"],
                            "is_error": payload["is_error"],
                        }
                        pending_call = None
                        events.append(event)
                        render_event(event, f"{msg_index}_{len(events)}")
                    elif kind == "chart":
                        try:
                            with open(payload, "rb") as f:
                                chart_bytes = f.read()
                        except OSError:
                            continue
                        event = {"type": "chart", "path": payload, "data": chart_bytes}
                        events.append(event)
                        render_event(event, f"{msg_index}_{len(events)}")
                    elif kind == "response":
                        event = {"type": "text", "text": payload}
                        events.append(event)
                        render_event(event, f"{msg_index}_{len(events)}")
            except anthropic.RateLimitError:
                message = "⚠️ Rate limited — wait a moment and try again."
                events.append({"type": "text", "text": message})
                st.error(message)
            except anthropic.APIConnectionError:
                message = "⚠️ Network error — check your connection and try again."
                events.append({"type": "text", "text": message})
                st.error(message)
            except anthropic.APIError as exc:
                message = f"⚠️ API error: {exc}"
                events.append({"type": "text", "text": message})
                st.error(message)
            except Exception as exc:
                message = f"⚠️ Unexpected error: {exc}"
                events.append({"type": "text", "text": message})
                st.error(message)

    st.session_state.messages.append({"role": "assistant", "events": events})


# ---------------------------------------------------------------- sidebar

with st.sidebar:
    st.header("📁 Data")

    uploaded = st.file_uploader("Upload a CSV file", type=["csv"])
    if uploaded is not None:
        file_key = (uploaded.name, uploaded.size)
        if st.session_state.loaded_file_key != file_key:
            try:
                df = pd.read_csv(uploaded)
            except Exception as exc:
                st.error(f"Failed to read '{uploaded.name}': {exc}")
            else:
                st.session_state.loaded_file_key = file_key
                load_data(df, uploaded.name)

    if st.button("Use Sample Data", width="stretch"):
        try:
            df = pd.read_csv(SAMPLE_DATA)
        except Exception as exc:
            st.error(f"Failed to load sample data: {exc}")
        else:
            st.session_state.loaded_file_key = None
            load_data(df, SAMPLE_DATA)

    if st.session_state.df is not None:
        df = st.session_state.df
        st.divider()
        st.subheader(st.session_state.filename or "dataset")
        col1, col2 = st.columns(2)
        col1.metric("Rows", f"{len(df):,}")
        col2.metric("Columns", df.shape[1])
        mem_mb = df.memory_usage(deep=True).sum() / 1024**2
        st.metric("Memory", f"{mem_mb:.2f} MB")
        st.caption("Columns")
        st.markdown(" ".join(f"`{c}`" for c in df.columns))

        st.divider()
        if st.button("🗑️ Clear Chat", width="stretch"):
            st.session_state.messages = []
            st.session_state.agent = DataAnalysisAgent(
                df, st.session_state.filename or "dataset"
            )
            st.rerun()

# ---------------------------------------------------------------- main area

st.title("📊 Data Analysis Agent")
st.caption("Upload a CSV and ask questions in natural language")

if st.session_state.df is None:
    st.info("⬅️ Upload a CSV file or click **Use Sample Data** in the sidebar to get started.")
    st.stop()

with st.expander("📄 Data Preview", expanded=False):
    st.dataframe(st.session_state.df.head(20), width="stretch")

# Replay chat history
for i, message in enumerate(st.session_state.messages):
    if message["role"] == "user":
        with st.chat_message("user"):
            st.markdown(message["content"])
    else:
        with st.chat_message("assistant"):
            for j, event in enumerate(message["events"]):
                render_event(event, f"{i}_{j}")

# Automatic initial overview after a dataset loads
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    run_agent_turn(prompt)

# User input
if user_prompt := st.chat_input("Ask a question about your data..."):
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)
    run_agent_turn(user_prompt)
