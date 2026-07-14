#!/usr/bin/env python3
"""Fire each market's 大盘复盘 once, shortly after that market closes — evaluated in the market's OWN
timezone. Run every 30 min from cron (which is PT); being tz-aware makes it DST- and day-boundary-proof
(this box's cron ignores CRON_TZ). Dedup via a small JSON state file keyed by the market's local date.

  python3 review_dispatcher.py          # normal (may fire)
  python3 review_dispatcher.py --dry     # log decisions only, never fire / never mark
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

# (region, IANA tz, close hour, close minute). Fire window = [close + FIRE_DELAY, close + WINDOW).
MARKETS = [
    ("cn", "Asia/Shanghai",    15, 0),   # A股 收盘 15:00
    ("hk", "Asia/Hong_Kong",   16, 0),   # 港股 收盘 16:00
    ("us", "America/New_York", 16, 0),   # 美股 收盘 16:00 ET
]
FIRE_DELAY_MIN = 5      # let EOD data settle after the bell
WINDOW_HOURS = 3       # still fire if a tick was missed, but not hours late / next session


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


def main() -> int:
    dry = "--dry" in sys.argv
    state = _load()
    changed = False
    for region, tzname, hh, mm in MARKETS:
        now = datetime.now(ZoneInfo(tzname))
        today = now.strftime("%Y-%m-%d")
        if now.weekday() >= 5:                                  # Sat/Sun in the market's own tz
            continue
        if state.get(region) == today:                         # already handled today
            continue
        fire_at = now.replace(hour=hh, minute=mm, second=0, microsecond=0) + timedelta(minutes=FIRE_DELAY_MIN)
        if not (fire_at <= now < fire_at + timedelta(hours=WINDOW_HOURS)):
            continue
        if dry:
            _log(f"[dry] WOULD fire {region} (local {today} {now:%H:%M} {tzname})")
            print(f"WOULD fire {region} @ local {today} {now:%H:%M} {tzname}")
            continue
        _log(f"dispatch {region} (local {today} {now:%H:%M} {tzname})")
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
