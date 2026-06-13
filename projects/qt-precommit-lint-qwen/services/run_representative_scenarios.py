import traceback
from datetime import datetime

from testing.event_replay_runner import run_event_replay
from testing.event_report_generator import generate_event_report

EVENTS = {
    "bear_2018": "2018-01-02",
    "covid_2020": "2020-02-03",
    "top_2021": "2021-02-18",
    "downtrend_2022": "2022-04-01",
    "ai_start_2023": "2023-01-03",
}


def run_all():
    summary = []
    start_time = datetime.now()

    for tag, start_date in EVENTS.items():
        print(f"\n=== Running scenario: {tag} ===")
        try:
            result, df = run_event_replay(start_date=start_date, months=6, tag=tag)

            report = generate_event_report(result, tag)
            path = f"docs/event_replay_{tag}_v1_0.md"

            with open(path, "w") as f:
                f.write(report)

            print(f"✅ Completed: {tag}")
            summary.append({**result, "scenario": tag})

        except Exception:
            print(f"❌ Failed: {tag}")
            print(traceback.format_exc())

    summary_path = "docs/event_replay_summary_v1_0.md"

    with open(summary_path, "w") as f:
        f.write("# Representative Scenario Summary v1.0\n\n")
        f.write(f"Run Time: {start_time}\n\n")
        for r in summary:
            f.write(f"## {r['scenario']}\n")
            f.write(f"- Start: {r['start_date']}\n")
            f.write(f"- End: {r['end_date']}\n")
            f.write(f"- Final Equity: {r['final_equity']}\n")
            f.write(f"- Max Drawdown: {r['max_drawdown']}\n")
            f.write(f"- Min Equity: {r['min_equity']}\n\n")

    print("\n✅ All scenarios completed.")
    print("Summary saved to:", summary_path)


if __name__ == "__main__":
    run_all()
