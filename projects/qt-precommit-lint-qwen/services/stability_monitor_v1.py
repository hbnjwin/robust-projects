import json
import os
from datetime import datetime

SNAPSHOT_DIR = "logs/stability_snapshots"
SUMMARY_FILE = "docs/event_replay_summary_v1_0.md"


def parse_summary():
    if not os.path.exists(SUMMARY_FILE):
        return None

    results = {}
    with open(SUMMARY_FILE, "r") as f:
        lines = f.readlines()

    current = None
    for line in lines:
        line = line.strip()
        if line.startswith("## "):
            current = line.replace("## ", "")
            results[current] = {}
        elif "Final Equity:" in line and current:
            results[current]["final_equity"] = float(line.split(":")[1].strip())
        elif "Max Drawdown:" in line and current:
            results[current]["max_drawdown"] = float(line.split(":")[1].strip())

    return results


def generate_snapshot():
    data = parse_summary()
    if data is None:
        print("No summary found.")
        return

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    snapshot = {"timestamp": datetime.now().isoformat(), "scenarios": data}

    filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.json")
    path = os.path.join(SNAPSHOT_DIR, filename)

    with open(path, "w") as f:
        json.dump(snapshot, f, indent=4)

    print(f"✅ Stability snapshot saved to {path}")


if __name__ == "__main__":
    generate_snapshot()
