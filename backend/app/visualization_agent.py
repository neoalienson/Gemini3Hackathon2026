"""
Data Visualization Agent: chooses chart type and generates ECharts config for each dataset.
"""
import csv
import json
import logging
from pathlib import Path
from typing import Any

from .visualization_tools import (
    generate_Bullet_Graph,
    generate_Dumbbell_Plot,
    generate_Joyplot,
    generate_Lollipop_Chart,
    generate_Slopegraph,
    generate_Sparklines,
)

logger = logging.getLogger(__name__)


def _load_csv(path: str) -> tuple[list[str], list[dict]]:
    """Load CSV, return (columns, rows as dicts)."""
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        cols = list(rows[0].keys()) if rows else []
        return cols, rows


def _load_json(path: str) -> list[dict]:
    """Load JSON array from file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else [data]


def _is_numeric_col(rows: list[dict], col: str) -> bool:
    """Return True if the column appears to contain numeric data."""
    if not rows or col not in (rows[0] or {}):
        return False
    numeric_count = 0
    total = 0
    for row in rows[:50]:  # Sample up to 50 rows
        v = row.get(col)
        if v is None or v == "":
            continue
        total += 1
        try:
            float(str(v).replace(",", ""))
            numeric_count += 1
        except (TypeError, ValueError):
            pass
    return total > 0 and numeric_count >= total * 0.8


def _infer_column_types(rows: list[dict], cols: list[str]) -> dict[str, str]:
    """Return {col_name: 'numeric'|'categorical'} for each column."""
    result = {}
    for col in cols:
        result[col] = "numeric" if _is_numeric_col(rows, col) else "categorical"
    return result


def _correct_category_value_cols(
    cols: list[str],
    rows: list[dict],
    cat: str,
    val: str,
) -> tuple[str, str]:
    """
    Ensure category_col is categorical and value_col is numeric.
    If LLM swapped them or passed wrong types, correct by picking appropriate columns.
    """
    types = _infer_column_types(rows, cols)
    numeric_cols = [c for c in cols if types.get(c) == "numeric"]
    cat_cols = [c for c in cols if types.get(c) == "categorical"]

    cat_valid = cat in cols and types.get(cat) == "categorical"
    val_valid = val in cols and types.get(val) == "numeric"

    if cat_valid and val_valid:
        return cat, val

    # Fix: pick categorical for category_col and numeric for value_col
    new_cat = cat if cat_valid else (cat_cols[0] if cat_cols else cols[0] if cols else "")
    new_val = val if val_valid else (numeric_cols[0] if numeric_cols else cols[-1] if len(cols) > 1 else cols[0] if cols else "")

    # If we had to swap (cat was numeric, val was categorical), use the corrected mapping
    if not cat_valid and cat in numeric_cols and not val_valid and val in cat_cols:
        new_cat, new_val = val, cat  # Swap: LLM had them backwards

    # Ensure we never use the same column for both
    if new_cat == new_val and cat_cols and numeric_cols:
        new_cat, new_val = cat_cols[0], numeric_cols[0]
    if new_cat and new_val and new_cat != new_val:
        return new_cat, new_val
    # Fallback: first categorical, first numeric
    if cat_cols and numeric_cols:
        return cat_cols[0], numeric_cols[0]
    if len(cols) >= 2:
        return cols[0], cols[1]
    return (cat or cols[0] if cols else "", val or cols[0] if cols else "")


def _correct_dumbbell_cols(
    cols: list[str],
    rows: list[dict],
    cat: str,
    v1: str,
    v2: str,
) -> tuple[str, str, str]:
    """Ensure category_col is categorical; value_col_1 and value_col_2 are numeric."""
    types = _infer_column_types(rows, cols)
    numeric_cols = [c for c in cols if types.get(c) == "numeric"]
    cat_cols = [c for c in cols if types.get(c) == "categorical"]

    new_cat = cat if (cat in cols and types.get(cat) == "categorical") else (cat_cols[0] if cat_cols else cols[0] if cols else "")
    valid_num = [c for c in [v1, v2] if c in cols and types.get(c) == "numeric"]
    remaining = [c for c in numeric_cols if c not in valid_num]
    new_v1 = v1 if (v1 in cols and types.get(v1) == "numeric") else (numeric_cols[0] if numeric_cols else "")
    new_v2 = v2 if (v2 in cols and types.get(v2) == "numeric") else (numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0] if numeric_cols else "")
    if new_v1 == new_v2 and len(numeric_cols) > 1:
        new_v1, new_v2 = numeric_cols[0], numeric_cols[1]
    return new_cat, new_v1, new_v2


def _correct_slopegraph_cols(
    cols: list[str],
    rows: list[dict],
    cat: str,
    start: str,
    end: str,
) -> tuple[str, str, str]:
    """Ensure category_col is categorical; start_col and end_col are numeric."""
    types = _infer_column_types(rows, cols)
    numeric_cols = [c for c in cols if types.get(c) == "numeric"]
    cat_cols = [c for c in cols if types.get(c) == "categorical"]

    new_cat = cat if (cat in cols and types.get(cat) == "categorical") else (cat_cols[0] if cat_cols else cols[0] if cols else "")
    new_start = start if (start in cols and types.get(start) == "numeric") else (numeric_cols[0] if numeric_cols else "")
    new_end = end if (end in cols and types.get(end) == "numeric") else (numeric_cols[1] if len(numeric_cols) > 1 else numeric_cols[0] if numeric_cols else "")
    if new_start == new_end and len(numeric_cols) > 1:
        new_start, new_end = numeric_cols[0], numeric_cols[1]
    return new_cat, new_start, new_end


def run_visualization_agent(csv_dir: str) -> list[dict]:
    """
    Load all CSV files + consolidation_result.json from csv_dir,
    use LLM to choose chart type per dataset, generate ECharts configs.
    Returns list of {title, chartType, echartsConfig, data}.
    """
    from genai.llm import generate_content

    datasets: list[dict[str, Any]] = []
    csv_dir_path = Path(csv_dir)

    for f in sorted(csv_dir_path.glob("*.csv")):
        cols, rows = _load_csv(str(f))
        if rows:
            col_types = _infer_column_types(rows, cols)
            datasets.append({"name": f.stem, "columns": cols, "column_types": col_types, "rows": rows[:100], "file": f.name})

    consolidation_path = csv_dir_path / "consolidation_result.json"
    if consolidation_path.exists():
        try:
            rows = _load_json(str(consolidation_path))
            if rows:
                cols = list(rows[0].keys()) if isinstance(rows[0], dict) else []
                col_types = _infer_column_types(rows, cols)
                datasets.append({"name": "Consolidation Result", "columns": cols, "column_types": col_types, "rows": rows[:100], "file": "consolidation_result.json"})
        except Exception as e:
            logger.warning("Failed to load consolidation result: %s", e)

    if not datasets:
        return []

    datasets_json = json.dumps(
        [
            {
                "name": d["name"],
                "columns": d["columns"],
                "column_types": d.get("column_types", {}),
                "sampleRows": d["rows"][:5],
            }
            for d in datasets
        ],
        indent=2,
    )

    prompt = f"""You are a data visualization expert. Given these datasets, for EACH dataset choose the best chart type and column mapping.

CRITICAL: Column types must match axis semantics:
- category_col: MUST be a CATEGORICAL/TEXT column (names, labels, IDs) - displayed as axis labels/categories
- value_col, value_col_1, value_col_2, start_col, end_col, target_col: MUST be NUMERIC columns (totals, amounts, counts)
Each dataset includes "column_types" showing which columns are "numeric" vs "categorical". Use them correctly.

## Available Chart Types and When to Use:
1. generate_Lollipop_Chart: Ranking many items. category_col=categorical (e.g. name), value_col=numeric (e.g. total_spent)
2. generate_Bullet_Graph: KPI with actual vs target. value_col=numeric, target_col=numeric (optional)
3. generate_Dumbbell_Plot: Compare two values per category. category_col=categorical, value_col_1/value_col_2=numeric
4. generate_Slopegraph: Change between two time points. category_col=categorical, start_col/end_col=numeric
5. generate_Joyplot: Distributions over groups/time. category_col=categorical, value_col=numeric, group_col=categorical (optional)
6. generate_Sparklines: Minimal trend. category_col=categorical, value_col=numeric

## Datasets:
{datasets_json}

## Your Task:
For each dataset, output one JSON object per line (NDJSON). Each line:
{{"dataset_name": "...", "chart_type": "Lollipop_Chart|Bullet_Graph|Dumbbell_Plot|Slopegraph|Joyplot|Sparklines", "category_col": "<categorical column>", "value_col": "<numeric column>", ...}}

ALWAYS: category_col = a categorical column; value_col = a numeric column. Match column_types.
Output exactly {len(datasets)} lines, one per dataset.
"""
    try:
        out = generate_content(prompt, temperature=0.0).strip()
    except Exception as e:
        logger.exception("Visualization LLM failed: %s", e)
        return []

    charts: list[dict] = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            spec = json.loads(line)
        except json.JSONDecodeError:
            continue
        dataset_name = spec.get("dataset_name", "")
        chart_type = spec.get("chart_type", "Lollipop_Chart")
        ds = next((d for d in datasets if d["name"] == dataset_name or d["file"].replace(".csv", "").replace(".json", "") == dataset_name.replace(" ", "_")), None)
        if not ds:
            ds = datasets[len(charts)] if len(charts) < len(datasets) else None
        if not ds:
            continue
        rows = ds["rows"]
        cols = ds["columns"]
        title = spec.get("title", ds["name"])
        try:
            if chart_type == "Lollipop_Chart":
                cat = spec.get("category_col") or (cols[0] if cols else "")
                val = spec.get("value_col") or (cols[1] if len(cols) > 1 else cols[0] if cols else "")
                cat, val = _correct_category_value_cols(cols, rows, cat, val)
                res = generate_Lollipop_Chart(rows, cat, val, title)
            elif chart_type == "Bullet_Graph":
                val = spec.get("value_col") or (cols[0] if cols else "")
                numeric_cols = [c for c in cols if _is_numeric_col(rows, c)]
                if val not in numeric_cols and numeric_cols:
                    val = numeric_cols[0]
                tgt = spec.get("target_col") if spec.get("target_col") in cols else None
                res = generate_Bullet_Graph(rows, val, tgt, title)
            elif chart_type == "Dumbbell_Plot":
                cat = spec.get("category_col") or (cols[0] if cols else "")
                v1 = spec.get("value_col_1") or (cols[1] if len(cols) > 1 else "")
                v2 = spec.get("value_col_2") or (cols[2] if len(cols) > 2 else cols[1] if len(cols) > 1 else "")
                cat, v1, v2 = _correct_dumbbell_cols(cols, rows, cat, v1, v2)
                res = generate_Dumbbell_Plot(rows, cat, v1, v2, title)
            elif chart_type == "Slopegraph":
                cat = spec.get("category_col") or (cols[0] if cols else "")
                start = spec.get("start_col") or (cols[1] if len(cols) > 1 else "")
                end = spec.get("end_col") or (cols[2] if len(cols) > 2 else cols[1] if len(cols) > 1 else "")
                cat, start, end = _correct_slopegraph_cols(cols, rows, cat, start, end)
                res = generate_Slopegraph(rows, cat, start, end, title)
            elif chart_type == "Joyplot":
                cat = spec.get("category_col") or (cols[0] if cols else "")
                val = spec.get("value_col") or (cols[1] if len(cols) > 1 else cols[0] if cols else "")
                cat, val = _correct_category_value_cols(cols, rows, cat, val)
                grp = spec.get("group_col") if spec.get("group_col") in cols else None
                res = generate_Joyplot(rows, cat, val, grp, title)
            elif chart_type == "Sparklines":
                cat = spec.get("category_col") or (cols[0] if cols else "")
                val = spec.get("value_col") or (cols[1] if len(cols) > 1 else cols[0] if cols else "")
                cat, val = _correct_category_value_cols(cols, rows, cat, val)
                res = generate_Sparklines(rows, cat, val, title)
            else:
                cat = cols[0] if cols else ""
                val = cols[1] if len(cols) > 1 else cols[0] if cols else ""
                cat, val = _correct_category_value_cols(cols, rows, cat, val)
                res = generate_Lollipop_Chart(rows, cat, val, title)
            charts.append(res)
        except Exception as e:
            logger.warning("Chart generation failed for %s: %s", dataset_name, e)
    return charts
