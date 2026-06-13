#!/usr/bin/env python3
"""afternoon_sync_wrapper.py — afternoon_sync cron 的纯执行层"""
import subprocess, sys, time, json, os, re
from pathlib import Path
from datetime import datetime, timezone, timedelta

LOG_FILE  = Path("/home/tulin/quant/logs/afternoon_sync_wrapper.log")
STATE_FILE = Path("/home/tulin/quant/control/task_state/afternoon_sync.json")
PID_FILE  = Path("/home/tulin/quant/run/afternoon_sync.pid")
VENV      = "/home/tulin/quant/.venv/bin/python"
SCRIPT_DIR = Path("/home/tulin/quant")
tz8 = timezone(timedelta(hours=8))

def log(msg):
    ts = datetime.now(tz8).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def run_bg(cmd, env=None):
    log(f"START bg: {cmd[5] if len(cmd)>5 else cmd[0]}...")
    env = env or os.environ.copy()
    proc = subprocess.Popen(
        cmd, stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT, cwd=str(SCRIPT_DIR), env=env,
        start_new_session=True
    )
    PID_FILE.write_text(str(proc.pid))
    return proc

def wait_bg(timeout=50*60, poll=30):
    elapsed = 0
    while elapsed < timeout:
        time.sleep(poll)
        elapsed += poll
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
        except (ValueError, FileNotFoundError, ProcessLookupError):
            log(f"BG done at {elapsed//60}m")
            return
        log(f"  still running... ({elapsed//60}m)")

def parse_log():
    text = LOG_FILE.read_text()
    m = re.search(r'Inserted rows: ([0-9,]+)', text)
    rows = int(m.group(1).replace(",","")) if m else 0
    m2 = re.search(r'\[([0-9]+)/([0-9]+)\]', text)
    total = int(m2.group(2)) if m2 else 0
    done  = int(m2.group(1)) if m2 else 0
    return rows, done, total

def write_state(status, rows=0, done=0, total=0, error=""):
    state = {
        "last_run": datetime.now(tz8).isoformat(),
        "status": status,
        "error": error,
        "stocks_updated": str(total),
        "rows_inserted": str(rows),
        "etf_rows_inserted": "0",
        "index_rows_inserted": "0",
        "fund_flow_rows_inserted": "0",
        "fund_flow_errors": "0"
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    log(f"task_state written: {status} (rows={rows}, done={done}/{total})")

def run_step(cmd, timeout=300):
    r = subprocess.run(cmd, capture_output=True, text=True,
                      timeout=timeout)
    out = r.stdout.strip()[-300:] if r.stdout else ""
    err = r.stderr.strip()[:200]   if r.stderr  else ""
    if r.returncode == 0:
        log(f"OK: {out}")
    else:
        log(f"WARN [{r.returncode}]: {err or out}")
    return r.returncode == 0

def main():
    log("=== wrapper started ===")

    # Step 1: 更新 stock_list.csv（用独立脚本，避免引号问题）
    log("Step 1: stock_list update...")
    update_script = Path("/home/tulin/quant/scripts/_update_stocklist.py")
    if not update_script.exists():
        update_script.write_text("""
import akshare as ak, pandas as pd
from pathlib import Path
df = ak.stock_info_a_code_name()
df['ts_code'] = df['code'].apply(lambda x: x+'.SH' if x.startswith('6') else x+'.SZ')
df = df[['ts_code','name']]
csv = '/home/tulin/quant/data/stock_list.csv'
if Path(csv).exists():
    old = pd.read_csv(csv)
    etf = old[old['ts_code'].str.split('.').str[0].str.match(r'^(1[0-5]|5[0-8]|56)')]
    df = pd.concat([df, etf], ignore_index=True).drop_duplicates('ts_code')
df.to_csv(csv, index=False)
print(f'stock_list OK: {len(df)}')
""")
    run_step([VENV, str(update_script)], timeout=60)

    # Step 2: 全市场增量同步（后台，log-every=500减少输出）
    today = datetime.now(tz8).strftime("%Y%m%d")
    bg_proc = run_bg([
        VENV, "data/import_full_market_akshare.py",
        "--log-every", "500",
        "--start-date", today,
        "--end-date",   today,
    ])
    log(f"BG pid={bg_proc.pid}, waiting up to 50min...")
    wait_bg(timeout=50*60, poll=30)
    rows, done, total = parse_log()
    log(f"Step 2 done: rows={rows}, done={done}/{total}")

    # Step 3: ETF
    log("Step 3: ETF sync...")
    run_step([VENV, "/home/tulin/quant/data/sync_etf_sina.py",
              "--start-date", today, "--end-date", today, "--workers", "4"], timeout=300)

    # Step 4: 指数
    log("Step 4: index sync...")
    run_step([VENV, "/home/tulin/quant/data/import_index_akshare.py"], timeout=300)

    # Step 5: 资金流
    log("Step 5: fund_flow sync...")
    run_step([VENV, "/home/tulin/quant/data/import_fund_flow_ths.py"], timeout=300)

    # 最终状态
    if done >= 6000 and rows >= 6000:
        write_state("success", rows, done, total)
    elif done >= 2000:
        write_state("partial", rows, done, total, "stocks_updated < 6000")
    else:
        write_state("error", rows, done, total, "stocks_updated < 2000")

    log("=== wrapper done ===")

if __name__ == "__main__":
    main()
