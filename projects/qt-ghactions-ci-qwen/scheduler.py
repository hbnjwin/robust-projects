import schedule
import time
import subprocess
from datetime import datetime


def job():
    print("\n[", datetime.now(), "] Running daily update + backtest...")
    subprocess.run(["python", "update_data_pg.py"])
    subprocess.run(["python", "run_backtest_pg.py"])
    print("[", datetime.now(), "] Job finished\n")


# 每天15:30执行（可调整）
schedule.every().day.at("15:30").do(job)

print("Scheduler started...")

while True:
    schedule.run_pending()
    time.sleep(60)
