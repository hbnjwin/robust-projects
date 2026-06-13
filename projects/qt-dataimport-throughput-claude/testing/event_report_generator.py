import datetime


def generate_event_report(result, tag):
    today = datetime.date.today()

    lines = []
    lines.append(f"# Event Replay Report - {tag}")
    lines.append(f"Generated: {today}\n")

    lines.append(f"Start Date: {result['start_date']}")
    lines.append(f"End Date: {result['end_date']}")
    lines.append(f"Final Equity: {result['final_equity']}")
    lines.append(f"Max Drawdown: {result['max_drawdown']}")
    lines.append(f"Min Equity: {result['min_equity']}\n")

    return "\n".join(lines)
