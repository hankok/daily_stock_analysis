#!/usr/bin/env python3
"""Fire each market's 大盘复盘 once, right after that market closes — evaluated in the market's OWN
timezone AND gated on a freshly-closed daily bar. Cron is PT and ignores CRON_TZ, so the tz-math here
(not the cron clock) decides when each market is due, which also makes it DST-proof. Asia has no DST, so
CN/HK close shifts an hour in PT between seasons — the cron covers both PT times and this script fires
the right one. Dedup via a small JSON state file keyed by the market's own local date.

Two gates must BOTH pass before a region fires:
  1. wall-clock window — now is within [close+FIRE_DELAY, close+WINDOW) in the market's tz, on a weekday.
  2. fresh daily bar   — the market's benchmark index has a DAILY bar dated today (market-local). This is
                         what stops a HOLIDAY / half-day-with-no-print / pre-finalization run from
                         generating a review off stale or partial data. Missing → skip, retry next tick.

Cron (PT, EVERY day — the tz weekday check handles market weekdays, including the PST day-boundary shift
where an Asian weekday close lands on the previous PT calendar day; do NOT restrict cron to Mon-Fri):
  5,35 0,1,13,23 * * *   .venv/bin/python review_dispatcher.py
    00:05 / 23:05 PT → CN   (close 15:00 CST = 00:00 PDT / 23:00 PST)
    00:05 / 01:05 PT → HK   (close 16:00 HKT = 00:00 PST / 01:00 PDT)
    13:05 PT         → US   (close 16:00 ET = 13:00 PT year-round)
  The :05 fires at close+5m; the :35 is a same-window retry if the bar wasn't final / the runner failed.

  python3 review_dispatcher.py          # normal (may fire)
  python3 review_dispatcher.py --dry    # log decisions only, never fire / never mark
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, "run_region_review.sh")
STATE = os.path.join(HERE, "logs", "review_dispatch_state.json")
LOG = os.path.join(HERE, "logs", "review_dispatcher.log")

# (region, IANA tz, close hour, close minute, benchmark index for the fresh-bar gate).
# The gate index is the SAME source the review reads its index close from, so "no fresh bar" here
# means the review would have had nothing current to report anyway.
MARKETS = [
    ("cn", "Asia/Shanghai",    15, 0, "000001.SS"),   # A股 收盘 15:00 · 上证综指
    ("hk", "Asia/Hong_Kong",   16, 0, "^HSI"),         # 港股 收盘 16:00 · 恒生指数
    ("us", "America/New_York", 16, 0, "^GSPC"),        # 美股 收盘 16:00 ET · 标普500
]
FIRE_DELAY_MIN = 5      # let EOD data settle after the bell
WINDOW_HOURS = 3        # still fire if a tick was missed, but not hours late / next session


def _log(msg: str) -> None:
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now().isoformat(timespec='seconds')}  {msg}\n")
    except Exception:
        pass


def _load() -> dict:
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save(d: dict) -> None:
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(d, fh)
    os.replace(tmp, STATE)


def _has_fresh_bar(sym: str, tzname: str, today_local) -> bool:
    """True iff `sym`'s latest DAILY bar is dated today in the market's tz — i.e. this session
    actually closed and printed a finalized bar. Fail-CLOSED: any error (network / import / empty)
    returns False, so a review whose close we can't confirm is deferred to the next tick rather than
    published off stale or partial data."""
    try:
        import yfinance as yf
        hist = yf.Ticker(sym).history(period="7d", auto_adjust=False)
        if hist is None or hist.empty:
            _log(f"  fresh-bar: {sym} returned no history")
            return False
        last = hist.index[-1]
        try:
            last_date = last.tz_convert(ZoneInfo(tzname)).date()   # tz-aware index → market-local date
        except (TypeError, AttributeError):
            last_date = last.date()
        if last_date != today_local:
            _log(f"  fresh-bar: {sym} latest daily bar {last_date} != market-today {today_local}")
            return False
        return True
    except Exception as e:
        _log(f"  fresh-bar: {sym} check error: {e}")
        return False


def main() -> int:
    dry = "--dry" in sys.argv
    state = _load()
    changed = False
    for region, tzname, hh, mm, idx_sym in MARKETS:
        now = datetime.now(ZoneInfo(tzname))
        today = now.strftime("%Y-%m-%d")
        if now.weekday() >= 5:                                  # Sat/Sun in the market's own tz
            continue
        if state.get(region) == today:                         # already handled today
            continue
        fire_at = now.replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(minutes=FIRE_DELAY_MIN)
        if not (fire_at <= now < fire_at + timedelta(hours=WINDOW_HOURS)):
            continue
        if not _has_fresh_bar(idx_sym, tzname, now.date()):     # NEW gate: require today's finalized bar
            _log(f"{region}: due but no finalized daily bar for {today} yet — skip, will retry ({tzname})")
            continue
        if dry:
            _log(f"[dry] WOULD fire {region} (local {today} {now:%H:%M} {tzname}, fresh bar OK)")
            print(f"WOULD fire {region} @ local {today} {now:%H:%M} {tzname} (fresh bar OK)")
            continue
        _log(f"dispatch {region} (local {today} {now:%H:%M} {tzname}, fresh bar OK)")
        try:
            rc = subprocess.run(["/bin/bash", RUNNER, region], timeout=1500).returncode
        except Exception as e:
            _log(f"  {region} runner error: {e}")
            rc = 1
        if rc == 0:
            state[region] = today
            changed = True
            _log(f"  {region} done — marked {today}")
        else:
            _log(f"  {region} rc={rc} — will retry next tick")
    if changed:
        _save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
