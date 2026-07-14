#!/bin/bash
# Generate ONE market's 大盘复盘 at its close, translate to English, NO email (web only).
# Writes reports/market_review_<region>_YYYYMMDD.md (+ .en.md). Usage: run_region_review.sh <cn|hk|us>
#
# Exit status = main.py's: non-zero when the review itself fails, so review_dispatcher.py leaves the
#   market UNMARKED and retries on the next 30-min tick (a failed run is no longer silently "done").
#   translate_brief.py is best-effort — its failure only means the .en.md lags, so it never fails the run.
# WEBUI_ENABLED=false: --market-review only writes a static report; skip main.py's redundant frontend
#   rebuild + FastAPI-on-:8000 serve attempt (the real dashboard already runs separately at boot).
region="${1:?usage: run_region_review.sh <cn|hk|us>}"
cd ~/daily_stock_analysis || exit 1
mkdir -p logs
{
  echo "=== $(date '+%F %T %Z') run_region_review $region ==="
  MARKET_REVIEW_REGION="$region" WEBUI_ENABLED=false .venv/bin/python main.py --market-review --no-notify
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "!!! $(date '+%F %T %Z') main.py rc=$rc for $region — NOT marking done, will retry next tick"
    exit "$rc"
  fi
  # zh report OK → translate to English for waveradar.us (best-effort; must not fail the run)
  /home/hanc/wave-radar/.venv/bin/python /home/hanc/wave-radar/engine/translate_brief.py --region "$region" \
    || echo "warn: $(date '+%F %T %Z') translate failed for $region (zh report still generated OK)"
} >> logs/cron_market_review.log 2>&1
