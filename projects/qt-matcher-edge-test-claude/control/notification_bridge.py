import os
import json
import time
import logging
from datetime import datetime

BASE_DIR = os.path.expanduser("~/quant")
STATE_DIR = os.path.join(BASE_DIR, "control/task_state")
LOG_PATH = os.path.join(BASE_DIR, "logs/notification_bridge.log")

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logger = logging.getLogger("notification_bridge")
logger.setLevel(logging.INFO)

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

_fh = logging.FileHandler(LOG_PATH)
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_ch = logging.StreamHandler()
_ch.setFormatter(_fmt)
logger.addHandler(_ch)


def scan_and_notify():
    if not os.path.isdir(STATE_DIR):
        logger.warning("State directory not found: %s", STATE_DIR)
        return

    for file in os.listdir(STATE_DIR):
        path = os.path.join(STATE_DIR, file)
        try:
            with open(path, "r") as f:
                state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Failed to read state file %s: %s", file, e)
            continue

        if state.get("notified") == False:
            task_name = file.replace(".json", "")
            status = state.get("status", "unknown")
            logger.info("Detected unnotified task: %s (status=%s)", task_name, status)

            # 标记已通知
            state["notified"] = True
            state["notified_at"] = str(datetime.now())

            try:
                with open(path, "w") as f:
                    json.dump(state, f, indent=4)
                logger.info("Marked task %s as notified", task_name)
            except IOError as e:
                logger.error("Failed to update state file %s: %s", file, e)


if __name__ == "__main__":
    logger.info("Notification Bridge Started")
    while True:
        scan_and_notify()
        time.sleep(60)
