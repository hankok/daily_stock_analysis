#!/bin/bash
# Generate ONE market's 大盘复盘 at its close, translate to English, NO email (web only).
# Writes reports/market_review_<region>_YYYYMMDD.md (+ .en.md). Usage: run_region_review.sh <cn|hk|us>
region="${1:?usage: run_region_review.sh <cn|hk|us>}"
cd ~/daily_stock_analysis || exit 1
mkdir -p logs
echo "=== $(date '+%F %T %Z') run_region_review $region ==="  >> logs/cron_market_review.log
MARKET_REVIEW_REGION="$region" .venv/bin/python main.py --market-review --no-notify >> logs/cron_market_review.log 2>&1
# translate just this region's fresh file to English for waveradar.us
/home/hanc/wave-radar/.venv/bin/python /home/hanc/wave-radar/engine/translate_brief.py --region "$region" >> logs/cron_market_review.log 2>&1
