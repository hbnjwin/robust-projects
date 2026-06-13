import json
import time
import subprocess
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.expanduser("~/quant"))
from utils.logger import get_logger

BASE_DIR = os.path.expanduser("~/quant")
REGISTRY_PATH = os.path.join(BASE_DIR, "control/task_registry.json")
STATE_DIR = os.path.join(BASE_DIR, "control/task_state")
HISTORY_DIR = os.path.join(BASE_DIR, "control/task_history")
PYTHON = os.path.expanduser("~/.venvs/quant_env/bin/python")

os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

logger = get_logger("scheduler_v2")


def log(msg):
    logger.info(msg)


def load_registry():
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def get_task_state(name):
    path = os.path.join(STATE_DIR, f"{name}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def should_run(task):
    now = datetime.now().strftime("%H:%M")
    if not task.get("enabled", False):
        return False
    if task["schedule"] != now:
        return False

    # 检查今天是否已经运行过
    state = get_task_state(task["name"])
    if state:
        last_run = state.get("last_run", "")
        today = datetime.now().strftime("%Y-%m-%d")
        if last_run.startswith(today):
            return False

    # 检查依赖
    dep = task.get("depends_on")
    if dep:
        dep_state = get_task_state(dep)
        if not dep_state or dep_state.get("status") != "success":
            log(f"⏳ {task['name']} blocked: dependency '{dep}' not successful")
            return False
        # 依赖必须是今天成功的
        today = datetime.now().strftime("%Y-%m-%d")
        if not dep_state.get("last_run", "").startswith(today):
            log(f"⏳ {task['name']} blocked: dependency '{dep}' not run today")
            return False

    return True


def run_task(task):
    name = task["name"]
    script_path = os.path.join(BASE_DIR, task["script"])
    state_path = os.path.join(STATE_DIR, f"{name}.json")
    now_str = str(datetime.now())

    log(f"▶ Running: {name}")

    retry_count = task.get("retry", 0)
    attempts = 0
    success = False

    while attempts <= retry_count:
        try:
            result = subprocess.run(
                [PYTHON, script_path],
                check=True,
                timeout=600,  # 10 分钟超时
                capture_output=True,
                text=True,
            )
            state = {"last_run": now_str, "status": "success", "attempt": attempts + 1}
            log(f"✅ {name} succeeded (attempt {attempts + 1})")
            success = True
            break
        except subprocess.TimeoutExpired:
            log(f"⏰ {name} timed out (attempt {attempts + 1})")
            state = {"last_run": now_str, "status": "timeout", "attempt": attempts + 1}
        except Exception as e:
            log(f"❌ {name} failed (attempt {attempts + 1}): {e}")
            state = {"last_run": now_str, "status": "failed", "error": str(e), "attempt": attempts + 1}
        attempts += 1

    with open(state_path, "w") as f:
        json.dump(state, f, indent=4)

    # 归档历史
    history_file = os.path.join(HISTORY_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(history_file, "w") as f:
        json.dump(state, f, indent=4)


if __name__ == "__main__":
    log("OpenClaw Scheduler v2 Started")
    while True:
        registry = load_registry()
        for task in registry:
            if should_run(task):
                run_task(task)
        time.sleep(60)
