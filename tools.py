"""Tool implementations for the Data Analysis Agent.

All tools operate on a module-level DataFrame loaded via load_dataframe().
Tabular sections in results are wrapped in [TABLE]...[/TABLE] markers as CSV
so display.py can render them as rich tables.
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # non-interactive backend; charts are saved, not shown
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from display import TABLE_END_MARKER, TABLE_MARKER

OUTPUT_DIR = "./outputs"

# Module-level state: the loaded dataset
_df: pd.DataFrame | None = None
_filepath: str | None = None


def load_dataframe(filepath: str) -> pd.DataFrame:
    """Load a CSV into module state and return it."""
    return set_dataframe(pd.read_csv(filepath), filepath)


def set_dataframe(df: pd.DataFrame, source: str = "<in-memory>") -> pd.DataFrame:
    """Install an already-loaded DataFrame as the active dataset."""
    global _df, _filepath
    # Best-effort datetime parsing for object columns that look like dates
    for col in df.columns:
        is_texty = df[col].dtype == object or pd.api.types.is_string_dtype(df[col])
        if is_texty and ("date" in col.lower() or "time" in col.lower()):
            try:
                df[col] = pd.to_datetime(df[col])
            except (ValueError, TypeError):
                pass
    _df = df
    _filepath = source
    return df


def get_dataframe() -> pd.DataFrame:
    if _df is None:
        raise RuntimeError("No dataset loaded. Load a CSV first.")
    return _df


def _table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    """Encode a DataFrame as a marked CSV block for display rendering."""
    if max_rows is not None and len(df) > max_rows:
        df = df.head(max_rows)
    return f"{TABLE_MARKER}\n{df.to_csv(index=False)}{TABLE_END_MARKER}"


# ---------------------------------------------------------------- tools


def data_overview() -> str:
    df = get_dataframe()
    dtypes = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(t) for t in df.dtypes],
            "missing": df.isna().sum().values,
            "missing_pct": (df.isna().mean() * 100).round(2).values,
        }
    )
    mem_mb = df.memory_usage(deep=True).sum() / 1024**2
    parts = [
        f"Shape: {len(df):,} rows × {df.shape[1]} columns",
        f"Memory usage: {mem_mb:.2f} MB",
        "",
        "Column types and missing values:",
        _table(dtypes),
        "",
        "First 5 rows:",
        _table(df.head(5)),
    ]
    return "\n".join(parts)


def describe_column(column_name: str) -> str:
    df = get_dataframe()
    if column_name not in df.columns:
        raise ValueError(
            f"Column '{column_name}' not found. Available columns: {', '.join(df.columns)}"
        )
    s = df[column_name]

    if pd.api.types.is_datetime64_any_dtype(s):
        return (
            f"Column '{column_name}' (datetime):\n"
            f"  Min date:   {s.min()}\n"
            f"  Max date:   {s.max()}\n"
            f"  Date range: {(s.max() - s.min()).days} days\n"
            f"  Missing:    {s.isna().sum()}"
        )

    if pd.api.types.is_numeric_dtype(s) and s.dtype != bool:
        q = s.quantile([0.25, 0.5, 0.75])
        return (
            f"Column '{column_name}' (numeric, {s.dtype}):\n"
            f"  Count:    {s.count()}\n"
            f"  Mean:     {s.mean():.4f}\n"
            f"  Median:   {s.median():.4f}\n"
            f"  Std:      {s.std():.4f}\n"
            f"  Min:      {s.min():.4f}\n"
            f"  25%:      {q.loc[0.25]:.4f}\n"
            f"  75%:      {q.loc[0.75]:.4f}\n"
            f"  Max:      {s.max():.4f}\n"
            f"  Skewness: {s.skew():.4f}\n"
            f"  Missing:  {s.isna().sum()}"
        )

    # categorical / boolean / object
    counts = s.value_counts().head(10)
    pct = (counts / len(s) * 100).round(2)
    top = pd.DataFrame({"value": counts.index.astype(str), "count": counts.values, "pct": pct.values})
    return (
        f"Column '{column_name}' (categorical, {s.dtype}):\n"
        f"  Unique values: {s.nunique()}\n"
        f"  Missing:       {s.isna().sum()}\n"
        f"Top values:\n{_table(top)}"
    )


_OPERATORS = ("==", "!=", ">", "<", ">=", "<=", "contains")


def filter_data(column: str, operator: str, value: str) -> str:
    df = get_dataframe()
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found. Available: {', '.join(df.columns)}")
    if operator not in _OPERATORS:
        raise ValueError(f"Operator must be one of {_OPERATORS}")

    s = df[column]
    if operator == "contains":
        mask = s.astype(str).str.contains(str(value), case=False, na=False)
    else:
        # Cast the incoming string value to match the column dtype
        if pd.api.types.is_datetime64_any_dtype(s):
            typed_value = pd.to_datetime(value)
        elif s.dtype == bool:
            typed_value = str(value).strip().lower() in ("true", "1", "yes")
        elif pd.api.types.is_numeric_dtype(s):
            typed_value = float(value)
        else:
            typed_value = str(value)
        ops = {
            "==": s == typed_value,
            "!=": s != typed_value,
            ">": s > typed_value,
            "<": s < typed_value,
            ">=": s >= typed_value,
            "<=": s <= typed_value,
        }
        mask = ops[operator]

    result = df[mask]
    pct = len(result) / len(df) * 100 if len(df) else 0
    out = f"{len(result):,} of {len(df):,} rows match ({pct:.1f}%)."
    if len(result):
        out += f"\nFirst 10 matching rows:\n{_table(result.head(10))}"
    return out


def correlation_analysis(columns: list[str] | None = None) -> str:
    df = get_dataframe()
    numeric = df.select_dtypes("number")
    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            raise ValueError(f"Columns not found: {', '.join(missing)}")
        non_numeric = [c for c in columns if c not in numeric.columns]
        if non_numeric:
            raise ValueError(f"Columns are not numeric: {', '.join(non_numeric)}")
        numeric = numeric[columns]
    if numeric.shape[1] < 2:
        raise ValueError("Need at least two numeric columns for correlation analysis.")

    corr = numeric.corr()
    matrix = corr.round(3).reset_index().rename(columns={"index": ""})

    findings = []
    cols = corr.columns
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) > 0.7:
                findings.append(f"  • {cols[i]} ↔ {cols[j]}: r = {r:.3f} (strong)")

    out = f"Correlation matrix ({numeric.shape[1]} numeric columns):\n{_table(matrix)}"
    if findings:
        out += "\nNotable correlations (|r| > 0.7):\n" + "\n".join(findings)
    else:
        out += "\nNo pairs with |r| > 0.7."
    return out


_AGG_FUNCTIONS = ("mean", "sum", "count", "median", "min", "max")


def group_statistics(group_by: str, agg_column: str, agg_function: str) -> str:
    df = get_dataframe()
    for col in (group_by, agg_column):
        if col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {', '.join(df.columns)}")
    if agg_function not in _AGG_FUNCTIONS:
        raise ValueError(f"agg_function must be one of {_AGG_FUNCTIONS}")

    grouped = (
        df.groupby(group_by)[agg_column]
        .agg(agg_function)
        .sort_values(ascending=False)
        .reset_index()
    )
    grouped.columns = [group_by, f"{agg_function}_{agg_column}"]
    return f"{agg_function}({agg_column}) by {group_by}:\n{_table(grouped)}"


_CHART_TYPES = ("histogram", "scatter", "bar", "line", "box", "heatmap")


def create_visualization(
    chart_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    group_by: str | None = None,
    title: str | None = None,
) -> str:
    df = get_dataframe()
    if chart_type not in _CHART_TYPES:
        raise ValueError(f"chart_type must be one of {_CHART_TYPES}")
    for col in (x_column, y_column, group_by):
        if col is not None and col not in df.columns:
            raise ValueError(f"Column '{col}' not found. Available: {', '.join(df.columns)}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 6))

    if chart_type == "histogram":
        if not x_column:
            raise ValueError("histogram requires x_column")
        sns.histplot(data=df, x=x_column, hue=group_by, ax=ax)
    elif chart_type == "scatter":
        if not (x_column and y_column):
            raise ValueError("scatter requires x_column and y_column")
        sns.scatterplot(data=df, x=x_column, y=y_column, hue=group_by, ax=ax)
    elif chart_type == "bar":
        if not x_column:
            raise ValueError("bar requires x_column")
        if y_column:
            data = df.groupby(x_column)[y_column].sum().sort_values(ascending=False).reset_index()
            sns.barplot(data=data, x=x_column, y=y_column, ax=ax)
        else:
            counts = df[x_column].value_counts().reset_index()
            sns.barplot(data=counts, x=x_column, y="count", ax=ax)
        ax.tick_params(axis="x", rotation=30)
    elif chart_type == "line":
        if not (x_column and y_column):
            raise ValueError("line requires x_column and y_column")
        data = df.sort_values(x_column)
        if group_by:
            sns.lineplot(data=data, x=x_column, y=y_column, hue=group_by, ax=ax)
        else:
            sns.lineplot(data=data, x=x_column, y=y_column, ax=ax)
    elif chart_type == "box":
        if not y_column:
            raise ValueError("box requires y_column (x_column optional for grouping)")
        sns.boxplot(data=df, x=x_column, y=y_column, hue=group_by, ax=ax)
        if x_column:
            ax.tick_params(axis="x", rotation=30)
    elif chart_type == "heatmap":
        numeric = df.select_dtypes("number")
        if numeric.shape[1] < 2:
            raise ValueError("heatmap requires at least two numeric columns")
        sns.heatmap(numeric.corr(), annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)

    chart_title = title or f"{chart_type} of {y_column or x_column or 'data'}"
    ax.set_title(chart_title)
    fig.tight_layout()

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in chart_title.lower())
    path = os.path.join(OUTPUT_DIR, f"{safe_name}.png")
    fig.savefig(path, dpi=120)
    plt.close(fig)

    parts = [f"{chart_type} chart", f"x={x_column}" if x_column else None,
             f"y={y_column}" if y_column else None, f"grouped by {group_by}" if group_by else None]
    desc = ", ".join(p for p in parts if p)
    return f"Chart saved: {path}\nDescription: {desc}. Title: '{chart_title}'."


_BLOCKED_TOKENS = (
    "import", "exec", "eval(", "os.", "sys.", "open(", "__", "subprocess", "shutil",
)


def run_custom_query(query: str) -> str:
    df = get_dataframe()
    lowered = query.lower()
    for token in _BLOCKED_TOKENS:
        if token in lowered:
            raise ValueError(f"Query blocked: contains disallowed token '{token}'")

    result = df.query(query)
    out = f"Query matched {len(result):,} of {len(df):,} rows."
    if len(result):
        out += f"\nFirst 20 rows:\n{_table(result.head(20))}"
    return out


# Dispatch table used by the agent loop
TOOL_FUNCTIONS = {
    "data_overview": data_overview,
    "describe_column": describe_column,
    "filter_data": filter_data,
    "correlation_analysis": correlation_analysis,
    "group_statistics": group_statistics,
    "create_visualization": create_visualization,
    "run_custom_query": run_custom_query,
}
