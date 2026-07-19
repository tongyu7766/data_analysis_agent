"""Anthropic API tool schemas for the Data Analysis Agent."""

TOOLS = [
    {
        "name": "data_overview",
        "description": (
            "Get a comprehensive overview of the loaded dataset including shape, column "
            "types, sample rows, missing value counts, and memory usage. Call this first "
            "when starting analysis to understand the full picture."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "describe_column",
        "description": (
            "Get detailed statistics for a single column. Numeric columns return mean, "
            "median, std, min/max, quartiles, and skewness. Categorical columns return "
            "unique count and top 10 value counts with percentages. Datetime columns "
            "return the date range."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column_name": {"type": "string", "description": "Name of the column to describe"}
            },
            "required": ["column_name"],
        },
    },
    {
        "name": "filter_data",
        "description": (
            "Filter the dataset by a condition on one column and preview matching rows. "
            "Returns the match count and the first 10 matching rows. Use 'contains' for "
            "case-insensitive substring matching on text columns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "column": {"type": "string", "description": "Column to filter on"},
                "operator": {
                    "type": "string",
                    "enum": ["==", "!=", ">", "<", ">=", "<=", "contains"],
                    "description": "Comparison operator",
                },
                "value": {
                    "type": "string",
                    "description": "Value to compare against (cast to the column's dtype automatically)",
                },
            },
            "required": ["column", "operator", "value"],
        },
    },
    {
        "name": "correlation_analysis",
        "description": (
            "Compute a correlation matrix over numeric columns and highlight strongly "
            "correlated pairs (|r| > 0.7). Pass specific columns, or omit to use all "
            "numeric columns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Numeric columns to include (optional; defaults to all numeric columns)",
                }
            },
            "required": [],
        },
    },
    {
        "name": "group_statistics",
        "description": (
            "Group the data by one column and aggregate another, sorted descending by the "
            "result. Use this for questions like 'total sales by category' or 'average "
            "price by region'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {"type": "string", "description": "Column to group by"},
                "agg_column": {"type": "string", "description": "Column to aggregate"},
                "agg_function": {
                    "type": "string",
                    "enum": ["mean", "sum", "count", "median", "min", "max"],
                    "description": "Aggregation function",
                },
            },
            "required": ["group_by", "agg_column", "agg_function"],
        },
    },
    {
        "name": "create_visualization",
        "description": (
            "Create a chart from the dataset and save it as a PNG under ./outputs/. "
            "Chart types: histogram (needs x), scatter (needs x and y), bar (needs x; "
            "y optional — sums y per x when given, else counts), line (needs x and y), "
            "box (needs y; x optional for grouping), heatmap (correlation of all numeric "
            "columns). Proactively create charts when they would help the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {
                    "type": "string",
                    "enum": ["histogram", "scatter", "bar", "line", "box", "heatmap"],
                    "description": "Type of chart to create",
                },
                "x_column": {"type": "string", "description": "Column for the x-axis"},
                "y_column": {"type": "string", "description": "Column for the y-axis"},
                "group_by": {"type": "string", "description": "Column to color/group by (hue)"},
                "title": {"type": "string", "description": "Chart title (also used for the filename)"},
            },
            "required": ["chart_type"],
        },
    },
    {
        "name": "run_custom_query",
        "description": (
            "Run a pandas DataFrame.query() expression against the dataset for filters the "
            "other tools can't express, e.g. \"quantity > 5 and customer_region == 'North'\". "
            "Returns the match count and first 20 rows. Only query syntax is allowed — no "
            "imports or function calls."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A pandas .query() expression, e.g. \"total_amount > 1000\"",
                }
            },
            "required": ["query"],
        },
    },
]
