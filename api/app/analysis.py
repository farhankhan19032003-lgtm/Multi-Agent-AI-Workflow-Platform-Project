"""Safe, built-in analytics the agents can call (no arbitrary code execution).

Each function validates table/column names against the tenant's real schema, then does the maths
with numpy/pandas and returns plain JSON-able dicts.
"""
import numpy as np
import pandas as pd

from . import tenantdb as tdb

FREQ = {"day": ("D", 7), "week": ("W-MON", 52), "month": ("MS", 12), "quarter": ("QS", 4), "year": ("YS", 1)}
AGG = {"sum": "SUM", "avg": "AVG", "count": "COUNT", "min": "MIN", "max": "MAX"}


def _check(tenant_id: str, table: str, *cols: str) -> dict[str, str]:
    types = dict(tdb.table_columns(tenant_id, table))
    if not types:
        raise ValueError(f"Unknown table '{table}'. Use list_tables to see what exists.")
    for c in cols:
        if c and c not in types:
            raise ValueError(f"Column '{c}' not found in '{table}'. Columns: {', '.join(types)}")
    return types


def _num(v):
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return round(float(v), 4)


# --------------------------------------------------------------------- forecast
def _fit_predict(y: np.ndarray, steps: int, m: int):
    """Linear trend (+ additive seasonality when there are >= 2 full seasons). Returns (pred, fitted, sigma, used_season)."""
    n = len(y)
    t = np.arange(n)
    seasonal = m > 1 and n >= 2 * m
    idx = np.zeros(max(m, 1))
    if seasonal:
        coef = np.polyfit(t, y, 1)
        resid = y - np.polyval(coef, t)
        idx = np.array([resid[i::m].mean() for i in range(m)])
        idx -= idx.mean()
        adj = y - idx[t % m]
        coef = np.polyfit(t, adj, 1)
        fitted = np.polyval(coef, t) + idx[t % m]
    else:
        coef = np.polyfit(t, y, 1) if n >= 3 else np.array([0.0, y.mean()])
        fitted = np.polyval(coef, t)
    sigma = float(np.std(y - fitted, ddof=2)) if n > 3 else float(np.std(y - fitted))
    tf = np.arange(n, n + steps)
    pred = np.polyval(coef, tf) + (idx[tf % m] if seasonal else 0)
    return pred, fitted, sigma, seasonal


def forecast(tenant_id: str, table: str, date_column: str, value_column: str,
             periods: int = 6, freq: str = "month", agg: str = "sum") -> dict:
    if freq not in FREQ or agg not in AGG:
        raise ValueError(f"freq must be one of {list(FREQ)}, agg one of {list(AGG)}")
    periods = max(1, min(int(periods), 36))
    _check(tenant_id, table, date_column, value_column)
    q = tdb.q
    sql = (f"SELECT date_trunc('{freq}', CAST({q(date_column)} AS TIMESTAMP)) AS p, "
           f"{AGG[agg]}({q(value_column)}) AS v FROM {q(table)} "
           f"WHERE {q(date_column)} IS NOT NULL GROUP BY 1 ORDER BY 1")
    df = tdb.query_df(tenant_id, sql, trusted=True)
    if len(df) < 4:
        raise ValueError(f"Need at least 4 {freq}s of history to forecast; found {len(df)}.")
    pandas_freq, m = FREQ[freq]
    s = df.set_index("p")["v"].astype(float)
    full = pd.date_range(s.index.min(), s.index.max(), freq=pandas_freq)
    s = s.reindex(full).interpolate(limit_direction="both")
    y, n = s.values, len(s)

    pred, _, sigma, seasonal = _fit_predict(y, periods, m)
    # honest back-test on the most recent points
    k = min(max(1, n // 5), 6)
    mape = None
    if n - k >= 4:
        bp, _, _, _ = _fit_predict(y[:-k], k, m)
        actual = y[-k:]
        mask = actual != 0
        if mask.any():
            mape = float(np.mean(np.abs((actual[mask] - bp[mask]) / actual[mask])) * 100)

    future_idx = pd.date_range(s.index[-1], periods=periods + 1, freq=pandas_freq)[1:]
    rows = []
    for h, (ts, p) in enumerate(zip(future_idx, pred), start=1):
        w = 1.28 * sigma * np.sqrt(1 + h / n)
        rows.append({"period": ts.date().isoformat(), "forecast": _num(p), "low": _num(p - w), "high": _num(p + w)})
    return {
        "table": table, "metric": f"{agg}({value_column}) per {freq}", "periods_used": n,
        "history_tail": [{"period": i.date().isoformat(), "value": _num(v)} for i, v in s.tail(12).items()],
        "forecast": rows,
        "method": "linear trend" + (f" + {m}-period seasonality" if seasonal else "") + ", 80% interval",
        "backtest_mape_pct": _num(mape),
        "caveat": "Simple statistical estimate from history only; it ignores promotions, price changes and other events.",
    }


# --------------------------------------------------------------------- anomalies
def anomalies(tenant_id: str, table: str, value_column: str, date_column: str = "",
              group_column: str = "", method: str = "iqr", top: int = 15) -> dict:
    types = _check(tenant_id, table, value_column, date_column, group_column)
    q = tdb.q
    cols = [value_column] + [c for c in (date_column, group_column) if c]
    df = tdb.query_df(tenant_id, f"SELECT {', '.join(q(c) for c in cols)} FROM {q(table)} "
                                 f"WHERE {q(value_column)} IS NOT NULL", limit=500000, trusted=True)
    x = pd.to_numeric(df[value_column], errors="coerce")
    df, x = df[x.notna()].copy(), x.dropna()
    if len(x) < 10:
        raise ValueError("Need at least 10 numeric values to look for anomalies.")
    med, mad = float(np.median(x)), float(np.median(np.abs(x - np.median(x))))
    scale = 1.4826 * mad if mad > 0 else float(x.std()) or 1.0
    z = (x - med) / scale
    if method == "zscore":
        mean, sd = float(x.mean()), float(x.std()) or 1.0
        z = (x - mean) / sd
        mask = z.abs() > 3
        bounds = {"low": _num(mean - 3 * sd), "high": _num(mean + 3 * sd)}
    else:
        q1, q3 = float(x.quantile(.25)), float(x.quantile(.75))
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        mask = (x < lo) | (x > hi)
        bounds = {"low": _num(lo), "high": _num(hi)}
    out = df[mask].assign(score=z[mask]).sort_values("score", key=lambda s: s.abs(), ascending=False).head(top)
    rows = [{k: (v.isoformat() if hasattr(v, "isoformat") else (_num(v) if isinstance(v, (float, np.floating)) else v))
             for k, v in r.items()} for r in out.to_dict("records")]
    return {"table": table, "column": value_column, "method": method, "rows_checked": int(len(x)),
            "anomaly_count": int(mask.sum()), "anomaly_pct": _num(100 * mask.mean()),
            "normal_range": bounds, "median": _num(med), "top_anomalies": rows,
            "note": "Outliers are unusual values, not necessarily errors or fraud. Verify each with the business."}


# --------------------------------------------------------------------- correlations
def correlations(tenant_id: str, table: str, columns: list[str] | None = None, top: int = 15) -> dict:
    types = _check(tenant_id, table, *(columns or []))
    num_cols = [c for c, t in types.items() if tdb._is_num(t)]
    cols = [c for c in (columns or num_cols) if c in num_cols][:30]
    if len(cols) < 2:
        raise ValueError("Need at least two numeric columns.")
    q = tdb.q
    df = tdb.query_df(tenant_id, f"SELECT {', '.join(q(c) for c in cols)} FROM {q(table)}", limit=200000, trusted=True)
    corr = df.corr(numeric_only=True)
    pairs = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            r = corr.loc[a, b]
            if pd.notna(r):
                pairs.append({"a": a, "b": b, "r": _num(r), "n": int(df[[a, b]].dropna().shape[0])})
    pairs.sort(key=lambda p: abs(p["r"] or 0), reverse=True)
    return {"table": table, "pairs": pairs[:top], "columns_used": cols,
            "note": "Pearson correlation shows linear association only, not causation."}


# --------------------------------------------------------------------- profile
def profile(tenant_id: str, table: str) -> dict:
    _check(tenant_id, table)
    d = tdb.describe(tenant_id, table, sample_rows=0)
    stats = []
    try:
        res = tdb.run_query(tenant_id, f"SUMMARIZE {tdb.q(table)}", limit=200)
        stats = [dict(zip(res["columns"], r)) for r in res["rows"]]
    except Exception:  # SUMMARIZE is a bonus; the stored profile is enough
        pass
    return {"table": table, "rows": d["rows"], "columns": d["columns"], "summary": stats}
