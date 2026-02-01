"""
ECharts visualization generators for each chart type.
Each function returns {echartsConfig, data, chartType} for frontend rendering.
"""
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> float:
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _get_cols(data: list[dict]) -> list[str]:
    if not data:
        return []
    return list(data[0].keys())


def generate_Lollipop_Chart(
    data: list[dict],
    category_col: str,
    value_col: str,
    title: str = "Lollipop Chart",
) -> dict:
    """Lollipop: line + dot. Good for ranking many items."""
    cats = [str(row.get(category_col, "")) for row in data]
    vals = [_safe_float(row.get(value_col, 0)) for row in data]
    cat_label = category_col.replace("_", " ").title()
    val_label = value_col.replace("_", " ").title()
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff"}},
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "grid": {"left": "12%", "right": "6%", "bottom": "10%", "top": "18%", "containLabel": True},
            "xAxis": {"type": "category", "name": cat_label, "nameLocation": "middle", "nameGap": 30, "nameTextStyle": {"color": "#fff"}, "data": cats, "axisLabel": {"color": "#fff"}, "axisLine": {"lineStyle": {"color": "rgba(255,255,255,0.3)"}}},
            "yAxis": {"type": "value", "name": val_label, "nameLocation": "middle", "nameGap": 60, "nameTextStyle": {"color": "#fff"}, "axisLabel": {"color": "#fff"}, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}},
            "series": [
                {"type": "bar", "barWidth": 4, "data": vals, "itemStyle": {"color": "transparent"}},
                {"type": "scatter", "data": [[i, v] for i, v in enumerate(vals)], "symbolSize": 12, "itemStyle": {"color": "#0ea5e9"}},
            ],
        },
        "data": data,
        "chartType": "lollipop",
        "title": title,
    }


def generate_Bullet_Graph(
    data: list[dict],
    value_col: str,
    target_col: str | None = None,
    title: str = "Bullet Graph",
) -> dict:
    """Bullet: actual vs target with qualitative ranges."""
    cols = _get_cols(data)
    cats = [str(row.get(cols[0], f"Item {i+1}")) for i, row in enumerate(data)] if cols else [f"Item {i+1}" for i in range(len(data))]
    vals = [_safe_float(row.get(value_col, 0)) for row in data]
    targets = [_safe_float(row.get(target_col, 0)) for row in data] if target_col and data and target_col in (data[0] or {}) else []
    val_label = value_col.replace("_", " ").title()
    cat_label = (cols[0] if cols else "Category").replace("_", " ").title()
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff"}},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "12%", "right": "6%", "bottom": "10%", "top": "18%", "containLabel": True},
            "xAxis": {"type": "value", "name": val_label, "nameLocation": "middle", "nameGap": 30, "nameTextStyle": {"color": "#fff"}, "max": max(vals) * 1.2 if vals else 100, "axisLabel": {"color": "#fff"}, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}},
            "yAxis": {"type": "category", "name": cat_label, "nameLocation": "middle", "nameGap": 90, "nameTextStyle": {"color": "#fff"}, "data": cats, "axisLabel": {"color": "#fff"}},
            "series": [
                {"type": "bar", "data": vals, "barWidth": "60%", "itemStyle": {"color": "#0ea5e9"}},
                *([{"type": "scatter", "data": [[t, i] for i, t in enumerate(targets) if t is not None], "symbolSize": 10, "itemStyle": {"color": "#ef4444"}, "z": 10}] if targets else []),
            ],
        },
        "data": data,
        "chartType": "bullet",
        "title": title,
    }


def generate_Dumbbell_Plot(
    data: list[dict],
    category_col: str,
    value_col_1: str,
    value_col_2: str,
    title: str = "Dumbbell Plot",
) -> dict:
    """Dumbbell: compare two values per category."""
    cats = [str(row.get(category_col, "")) for row in data]
    v1 = [_safe_float(row.get(value_col_1, 0)) for row in data]
    v2 = [_safe_float(row.get(value_col_2, 0)) for row in data]
    cat_label = category_col.replace("_", " ").title()
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff"}},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": [value_col_1, value_col_2], "textStyle": {"color": "#fff"}, "top": "bottom"},
            "grid": {"left": "12%", "right": "6%", "bottom": "15%", "top": "18%", "containLabel": True},
            "xAxis": {"type": "value", "name": "Value", "nameLocation": "middle", "nameGap": 30, "nameTextStyle": {"color": "#fff"}, "axisLabel": {"color": "#fff"}, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}},
            "yAxis": {"type": "category", "name": cat_label, "nameLocation": "middle", "nameGap": 90, "nameTextStyle": {"color": "#fff"}, "data": cats, "axisLabel": {"color": "#fff"}},
            "series": [
                {"type": "bar", "name": value_col_1, "data": v1, "barWidth": "35%", "itemStyle": {"color": "#0ea5e9"}, "barGap": "-100%"},
                {"type": "bar", "name": value_col_2, "data": v2, "barWidth": "35%", "itemStyle": {"color": "#f59e0b"}},
            ],
        },
        "data": data,
        "chartType": "dumbbell",
        "title": title,
    }


def generate_Slopegraph(
    data: list[dict],
    category_col: str,
    start_col: str,
    end_col: str,
    title: str = "Slopegraph",
) -> dict:
    """Slopegraph: change between two points in time."""
    cats = [str(row.get(category_col, "")) for row in data]
    start_vals = [_safe_float(row.get(start_col, 0)) for row in data]
    end_vals = [_safe_float(row.get(end_col, 0)) for row in data]
    cat_label = category_col.replace("_", " ").title()
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff"}},
            "tooltip": {"trigger": "axis"},
            "grid": {"left": "12%", "right": "8%", "bottom": "10%", "top": "18%", "containLabel": True},
            "xAxis": {"type": "value", "name": f"{start_col} / {end_col}".replace("_", " ").title(), "nameLocation": "middle", "nameGap": 30, "nameTextStyle": {"color": "#fff"}, "axisLabel": {"color": "#fff"}, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}},
            "yAxis": {"type": "category", "name": cat_label, "nameLocation": "middle", "nameGap": 90, "nameTextStyle": {"color": "#fff"}, "data": cats, "axisLabel": {"color": "#fff"}},
            "series": [
                {"type": "line", "data": start_vals, "name": start_col, "symbol": "circle", "symbolSize": 8, "itemStyle": {"color": "#0ea5e9"}, "lineStyle": {"width": 2}},
                {"type": "line", "data": end_vals, "name": end_col, "symbol": "circle", "symbolSize": 8, "itemStyle": {"color": "#10b981"}, "lineStyle": {"width": 2}},
            ],
        },
        "data": data,
        "chartType": "slopegraph",
        "title": title,
    }


def generate_Joyplot(
    data: list[dict],
    category_col: str,
    value_col: str,
    group_col: str | None = None,
    title: str = "Joyplot",
) -> dict:
    """Joyplot: stacked area distributions over time/groups."""
    cols = _get_cols(data)
    if group_col and group_col in cols:
        groups = sorted(set(str(row.get(group_col, "")) for row in data))
    else:
        groups = ["All"]
        group_col = None
    cats = sorted(set(str(row.get(category_col, "")) for row in data)) if category_col in cols else [str(i) for i in range(len(data))]
    series = []
    colors = ["#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]
    for gi, g in enumerate(groups):
        subset = [row for row in data if not group_col or str(row.get(group_col, "")) == g]
        vals = [_safe_float(row.get(value_col, 0)) for row in subset]
        if not vals:
            continue
        series.append({"name": g, "type": "line", "stack": "Total", "areaStyle": {"opacity": 0.5, "color": colors[gi % len(colors)]}, "data": vals})
    max_len = max(len(s.get("data", [])) for s in series) if series else 0
    xdata = cats[:max_len] if len(cats) >= max_len else [str(i) for i in range(max_len)] if max_len else []
    if not xdata and series:
        xdata = [str(i) for i in range(len(series[0].get("data", [])))]
    cat_label = category_col.replace("_", " ").title() if category_col else "Category"
    val_label = value_col.replace("_", " ").title() if value_col else "Value"
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff"}},
            "tooltip": {"trigger": "axis"},
            "legend": {"top": "bottom", "textStyle": {"color": "#fff"}},
            "grid": {"left": "12%", "right": "6%", "bottom": "15%", "top": "18%", "containLabel": True},
            "xAxis": {"type": "category", "name": cat_label, "nameLocation": "middle", "nameGap": 30, "nameTextStyle": {"color": "#fff"}, "boundaryGap": False, "data": xdata, "axisLabel": {"color": "#fff"}},
            "yAxis": {"type": "value", "name": val_label, "nameLocation": "middle", "nameGap": 60, "nameTextStyle": {"color": "#fff"}, "axisLabel": {"color": "#fff"}, "splitLine": {"lineStyle": {"color": "rgba(255,255,255,0.1)"}}},
            "series": series if series else [{"type": "line", "data": [], "areaStyle": {}}],
        },
        "data": data,
        "chartType": "joyplot",
        "title": title,
    }


def generate_Sparklines(
    data: list[dict],
    category_col: str,
    value_col: str,
    title: str = "Sparkline",
) -> dict:
    """Sparklines: minimal trend inline."""
    cats = [str(row.get(category_col, "")) for row in data]
    vals = [_safe_float(row.get(value_col, 0)) for row in data]
    cat_label = category_col.replace("_", " ").title() if category_col else "Category"
    val_label = value_col.replace("_", " ").title() if value_col else "Value"
    return {
        "echartsConfig": {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#fff", "fontSize": 12}},
            "tooltip": {"trigger": "axis", "formatter": f"{cat_label}: {{b}} | {val_label}: {{c}}"},
            "grid": {"left": "2%", "right": "2%", "top": "15%", "bottom": "2%", "containLabel": False},
            "xAxis": {"type": "category", "name": cat_label, "show": False, "data": cats},
            "yAxis": {"type": "value", "name": val_label, "show": False},
            "series": [{"type": "line", "data": vals, "symbol": "none", "lineStyle": {"width": 2, "color": "#0ea5e9"}, "areaStyle": {"opacity": 0.2, "color": "#0ea5e9"}}],
        },
        "data": data,
        "chartType": "sparkline",
        "title": title,
    }
