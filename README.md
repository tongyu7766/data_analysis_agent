# 📊 Data Analysis Agent

A Python data analysis agent powered by Claude. Load a CSV file and analyze it through natural language conversation — the agent picks the right tools, runs statistics, creates charts, and explains the results.

Built with a transparent, hand-written agent loop (no LangChain), the `anthropic` SDK for tool use, `pandas` for data manipulation, `matplotlib`/`seaborn` for charts, and `rich` for polished terminal output.

## Features

- **7 analysis tools**: data overview, column statistics, filtering, correlation analysis, group aggregation, visualization, and custom pandas queries
- **Agentic loop**: Claude chains multiple tools in one turn to answer complex questions
- **Rich terminal UI**: panels, tables, spinners, and markdown rendering
- **Charts saved as PNG** to `./outputs/`

## Installation

```bash
pip install -r requirements.txt
```

## Setup

Set your Anthropic API key:

```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

## Usage

Generate the sample dataset (only needed once):

```bash
python generate_sample_data.py
```

Run the agent:

```bash
python agent.py
```

- Press **Enter** at the file prompt to use `sample_data.csv`, or type a path to your own CSV file.
- The agent starts with an automatic data overview, then you can ask questions:
  - *"Which category drives the most revenue?"*
  - *"How do sales vary by region? Show me a chart."*
  - *"Is there a correlation between quantity and total amount?"*
  - *"Show me orders over 1000 that were returned."*
- Type `quit` or `exit` to leave. Charts are saved in `./outputs/`.

## Web Interface

Run the Streamlit app:

```bash
streamlit run app.py
```

Open http://localhost:8501 in your browser. Upload a CSV or use the built-in sample data, then ask questions in natural language.

### Features
- Drag-and-drop CSV upload
- Real-time tool call visibility (expandable panels)
- Inline chart display with download option
- Full conversation history
- Dark theme

## Using your own CSV

Any CSV works. Columns whose names contain `date` or `time` are auto-parsed as datetimes. Just run `python agent.py` and enter the path.

## Project Structure

```
data_analysis_agent/
├── agent.py                  # CLI entry point (terminal rendering)
├── app.py                    # Streamlit web app entry point
├── agent_core.py             # Shared agent loop (used by CLI and web app)
├── tools.py                  # Tool implementations (pandas)
├── tool_schemas.py           # Anthropic API tool schemas
├── display.py                # Rich terminal display helpers
├── generate_sample_data.py   # Sample dataset generator
├── .streamlit/config.toml    # Streamlit theme (dark) + upload limit
├── requirements.txt
├── sample_data.csv           # 200 rows of e-commerce sales data
└── outputs/                  # Generated charts (auto-created)
```
