import json
import time
import subprocess
from datetime import datetime
import os

BASE_DIR = os.path.expanduser("~/quant")
REGISTRY_PATH = os.path.join(BASE_DIR, "control/task_registry.json")
STATE_DIR = os.path.join(BASE_DIR, "control/task_state")
PYTHON = os.path.expanduser("~/.venvs/quant_env/bin/python")


def load_registry():
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)


def should_run(task):
    now = datetime.now().strftime("%H:%M")
    return task["enabled"] and task["schedule"] == now


def run_task(task):
    script_path = os.path.join(BASE_DIR, task["script"])
    state_path = os.path.join(STATE_DIR, f"{task['name']}.json")

    try:
        subprocess.run([PYTHON, script_path], check=True)
        state = {
            "last_run": str(datetime.now()),
            "status": "success"
        }
    except Exception as e:
        state = {
            "last_run": str(datetime.now()),
            "status": "failed",
            "error": str(e)
        }

    with open(state_path, "w") as f:
        json.dump(state, f, indent=4)


if __name__ == "__main__":
    print("OpenClaw Scheduler Started")
    while True:
        registry = load_registry()
        for task in registry:
            if should_run(task):
                run_task(task)
        time.sleep(60)
