import os
import json
from datetime import datetime

SNAPSHOT_DIR = "logs/stability_snapshots"
REPORT_DIR = "logs/daily_reports"

os.makedirs(REPORT_DIR, exist_ok=True)

# 找到最新快照
files = sorted(os.listdir(SNAPSHOT_DIR))
if not files:
    print("No snapshot found.")
    exit()

latest = files[-1]
with open(os.path.join(SNAPSHOT_DIR, latest), "r") as f:
    data = json.load(f)

report_date = datetime.now().strftime("%Y-%m-%d")
report_path = os.path.join(REPORT_DIR, f"{report_date}.md")

with open(report_path, "w") as f:
    f.write(f"# 每日风险报告 - {report_date}\n\n")
    f.write(f"生成时间: {data['timestamp']}\n\n")
    f.write("## 场景回测摘要\n\n")

    for scenario, metrics in data["scenarios"].items():
        f.write(f"### {scenario}\n")
        f.write(f"- Final Equity: {metrics.get('final_equity', 'N/A')}\n")
        f.write(f"- Max Drawdown: {metrics.get('max_drawdown', 'N/A')}\n\n")

    f.write("---\n")
    f.write("本报告基于真实成交约束与多账户架构生成。\n")

print(f"✅ Markdown report generated: {report_path}")
