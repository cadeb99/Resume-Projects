# scheduler.py — weekly runner with logging
import schedule
import time
import logging
import os
from datetime import datetime
from config import SCHEDULE_DAY, SCHEDULE_TIME, DEMO_MODE

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(f"logs/run_{datetime.utcnow().strftime('%Y%m')}.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def run_pipeline() -> None:
    log.info(f"Pipeline started — {'DEMO' if DEMO_MODE else 'LIVE'} mode")
    try:
        from aggregator import aggregate
        from analyzer import analyze
        from emailer import deliver

        log.info("Step 1/3: Aggregating data...")
        dataset = aggregate()
        if dataset.get("has_errors"):
            log.warning(f"Data source errors: {dataset['source_errors']}")

        log.info("Step 2/3: Analyzing with Claude...")
        analysis = analyze(dataset)
        if analysis.get("status") == "error":
            log.error(f"Analysis failed: {analysis.get('error')}")
            # Still deliver with whatever we have
            analysis = {"status": "error", "analysis": {}}

        log.info("Step 3/3: Delivering email...")
        deliver(dataset, analysis)

        log.info("✅ Pipeline complete")

    except Exception as e:
        log.exception(f"Pipeline failed: {e}")


def start_scheduler() -> None:
    day = SCHEDULE_DAY.lower()
    time_str = SCHEDULE_TIME

    log.info(f"Scheduler starting — will run every {day.capitalize()} at {time_str}")

    getattr(schedule.every(), day).at(time_str).do(run_pipeline)

    log.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--now":
        log.info("Manual run triggered via --now flag")
        run_pipeline()
    else:
        start_scheduler()
