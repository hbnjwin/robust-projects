from fastapi import FastAPI
from datetime import datetime
import json
import os
import glob

app = FastAPI()

SIGNAL_DIR = "logs/signals"


def load_signal():
    """读取 logs/signals/ 目录下最新的 JSON 文件"""
    if not os.path.isdir(SIGNAL_DIR):
        return None

    files = glob.glob(os.path.join(SIGNAL_DIR, "*.json"))
    if not files:
        return None

    latest = max(files, key=os.path.getmtime)
    try:
        with open(latest, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


@app.get("/signal")
def get_signal():
    signal = load_signal()
    return {
        "timestamp": datetime.now().isoformat(),
        "signal": signal
    }


@app.get("/status")
def status():
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }
