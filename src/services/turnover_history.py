"""两市成交额历史 — the baseline the daily review needs to judge 量能 relatively.

WHY THIS EXISTS
---------------
`_describe_turnover` used to label turnover off an absolute ladder (>=15000亿 -> 高活跃度).
That ladder was written when 2万亿 was a big day, so by 2026 it maps 2.5万亿 and 1.5万亿 to the
same words, and the review model — handed one number with no reference frame — supplies its own
stale anchor and writes 天量. The fix is to hand it the distribution: where today sits against
the last ~6 months, yesterday, and this week.

SOURCE
------
The exchanges' own daily summaries (sse.com.cn / szse.cn via akshare), not an index proxy and
not Eastmoney:
  * Eastmoney is blocked from this host (push2his -> connection aborted).
  * Sina's index history carries no amount column at all.
  * Tencent's index `amount` is volume, not turnover — measured against 21 known days it drifts
    30% in five weeks, which a real unit conversion would not.
  * 沪 + 深 official summaries reproduce this box's own logged totals to -0.50% with a 0.05%
    stdev across those same 21 days. The constant ~0.5% shortfall is 北交所, which the two
    exchange summaries exclude; SCALE corrects for it so backfilled history and the numbers the
    review reports live on one basis.
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # src/
_ROOT = os.path.dirname(_HERE)
CACHE_PATH = os.environ.get(
    "TURNOVER_HISTORY_PATH", os.path.join(_ROOT, "data", "turnover_history.json"))

# 沪+深 official summaries / this box's own two-market total, measured over 21 overlapping
# sessions: mean 0.9950, stdev 0.0005. Dividing by it puts backfill on the same basis as the
# live figure, so a percentile computed across both is not reading a 0.5% step change.
SCALE = 0.9950
BASELINE_SESSIONS = 120        # ~6 months of trading days
WEEK_SESSIONS = 5


def _sse_yi(ymd: str) -> Optional[float]:
    import akshare as ak
    df = ak.stock_sse_deal_daily(date=ymd)
    row = df[df["单日情况"] == "成交金额"]
    return float(row["股票"].iloc[0]) if len(row) else None


def _szse_yi(ymd: str) -> Optional[float]:
    import akshare as ak
    df = ak.stock_szse_summary(date=ymd)
    row = df[df["证券类别"] == "股票"]
    return float(row["成交金额"].iloc[0]) / 1e8 if len(row) else None


def load() -> Dict[str, float]:
    try:
        with open(CACHE_PATH, encoding="utf-8") as fh:
            return {k: float(v) for k, v in json.load(fh).items()}
    except Exception:
        return {}


def save(hist: Dict[str, float]) -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(dict(sorted(hist.items())), fh, ensure_ascii=False, indent=0)
    os.replace(tmp, CACHE_PATH)


def record_today(date: str, total_amount_yi: float) -> None:
    """Store the figure the review itself just used, so the series keeps growing without a fetch.

    This is the authoritative number for that day (it includes 北交所), so it OVERWRITES any
    backfilled value for the same date rather than deferring to it."""
    if not date or not total_amount_yi or total_amount_yi <= 0:
        return
    try:
        hist = load()
        hist[str(date)[:10]] = round(float(total_amount_yi), 1)
        save(hist)
    except Exception as e:                                   # never break a review over the cache
        logger.warning("[量能] record_today failed: %s", e)


def backfill(days_back: int = 400, sleep: float = 0.4, verbose: bool = False) -> Dict[str, float]:
    """Fetch any missing sessions in the window. Weekends are skipped outright; a holiday simply
    returns nothing and is remembered as absent so it is not refetched every run."""
    hist = load()
    today = _dt.date.today()
    added = 0
    for i in range(days_back, -1, -1):
        d = today - _dt.timedelta(days=i)
        if d.weekday() >= 5:
            continue
        key = d.isoformat()
        if key in hist:
            continue
        ymd = key.replace("-", "")
        try:
            a, b = _sse_yi(ymd), _szse_yi(ymd)
        except Exception:
            continue                                          # holiday / not published
        if not a or not b:
            continue
        hist[key] = round((a + b) / SCALE, 1)
        added += 1
        if verbose:
            print("%s  %.1f 亿" % (key, hist[key]))
        if added % 20 == 0:
            save(hist)
        time.sleep(sleep)
    save(hist)
    logger.info("[量能] backfill added %d sessions, %d total", added, len(hist))
    return hist


def context(total_amount_yi: float, asof: str = "") -> Optional[dict]:
    """Where today's turnover sits against its own recent history.

    Returns None when there is not enough history to say anything honest — the caller must then
    NOT characterise the level, rather than fall back to an absolute claim."""
    hist = load()
    if not hist:
        return None
    asof = (asof or _dt.date.today().isoformat())[:10]
    past = [(k, v) for k, v in sorted(hist.items()) if k < asof and v > 0]
    if len(past) < 20:
        return None
    window = past[-BASELINE_SESSIONS:]
    vals = sorted(v for _, v in window)
    n = len(vals)
    med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    pct = sum(1 for v in vals if v < total_amount_yi) / n * 100
    prev_d, prev_v = past[-1]
    week = [v for _, v in past[-WEEK_SESSIONS:]]
    week_avg = sum(week) / len(week)
    return {
        "sessions": n,
        "median": round(med, 0),
        "p25": round(vals[int(n * 0.25)], 0),
        "p75": round(vals[int(n * 0.75)], 0),
        "max": round(vals[-1], 0),
        "percentile": round(pct, 0),
        "vs_median_pct": round((total_amount_yi / med - 1) * 100, 1),
        "prev_date": prev_d,
        "prev": round(prev_v, 0),
        "vs_prev_pct": round((total_amount_yi / prev_v - 1) * 100, 1),
        "week_avg": round(week_avg, 0),
        "vs_week_pct": round((total_amount_yi / week_avg - 1) * 100, 1),
    }


def describe(total_amount_yi: float, ctx: Optional[dict]) -> str:
    """A RELATIVE label. Without history it says so instead of inventing a level."""
    if not total_amount_yi or total_amount_yi <= 0:
        return "暂无数据"
    if not ctx:
        return "量能基准数据不足，暂不判断高低"
    p = ctx["percentile"]
    if p >= 90:
        band = "近半年极高位"
    elif p >= 70:
        band = "高于近半年多数交易日"
    elif p >= 30:
        band = "近半年中枢附近"
    elif p >= 10:
        band = "低于近半年多数交易日"
    else:
        band = "近半年极低位"
    return "%s（%d个交易日中分位 %d%%，较中位数 %+.1f%%）" % (band, ctx["sessions"], p, ctx["vs_median_pct"])


if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    h = backfill(days_back=days, verbose=True)
    print("total sessions:", len(h))
