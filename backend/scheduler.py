"""
scheduler.py
Runs the full AIRIX pipeline once daily, unattended — satisfies the
problem statement's requirement for scheduled daily extraction. Each
stage is a subprocess call to the existing pipeline scripts so this file
adds scheduling only, without duplicating pipeline logic.
"""
import subprocess
import sys
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

PIPELINE_STAGES = [
    "generate_data.py",
    "clean_data.py",
    "calculate_dgca_weights.py",
    "calculate_index.py",
    "backtest_index.py",
    "load_to_database.py",
]

DAILY_RUN_HOUR = 2  # 02:00 local time — off-peak


def run_pipeline():
    print(f"[{datetime.now().isoformat()}] Starting AIRIX daily pipeline run...")
    for stage in PIPELINE_STAGES:
        print(f"  -> {stage}")
        result = subprocess.run([sys.executable, stage])
        if result.returncode != 0:
            print(f"  !! {stage} failed with exit code {result.returncode}; aborting run.")
            return
    print(f"[{datetime.now().isoformat()}] Pipeline run complete.")


if __name__ == "__main__":
    scheduler = BlockingScheduler()
    scheduler.add_job(run_pipeline, "cron", hour=DAILY_RUN_HOUR, id="airix_daily_pipeline")
    print(f"AIRIX scheduler started. Daily run scheduled at {DAILY_RUN_HOUR:02d}:00.")
    run_pipeline()  # run once immediately so a demo has fresh data
    scheduler.start()
