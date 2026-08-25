"""Generate the synthetic site conditions log.

Weather and workforce used to reach the schedule analysis as caller-supplied
numbers: a client passed `weather_impact_days={"T-160": 4}` and the explanation
said "synthetic weather impact adds 4 days". Nothing said where the 4 came from,
which is the one thing this project claims to always answer.

This writes a daily site record instead - one row per crew-day, each with a
weather condition, whether the day was lost, and planned against present crew.
The schedule reads the log and derives both figures from it, so every delay day
points at the dated rows that produced it.

Deterministic: no randomness, so regenerating gives byte-identical output.
"""

import csv
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT = ROOT / "data" / "synthetic_epc" / "site_conditions" / "site_conditions_log.csv"

PROJECT = "atlas-demo-dc-01"
CLASSIFICATION = "SYNTHETIC EPC DEMO DATA — NOT A REAL SITE RECORD"

# Field work windows, taken from the schedule CSV so the log and the schedule
# describe the same job. Commissioning windows use the forecast dates because
# that is when the crew is actually expected on site.
WINDOWS = {
    "T-150": (date(2026, 5, 1), date(2026, 5, 22), "Electrical room ready", 8),
    "T-230": (date(2026, 5, 25), date(2026, 6, 8), "Install and test UPS-A", 4),
    "T-160": (date(2026, 6, 25), date(2026, 7, 3), "Install SWGR-A", 10),
    "T-170": (date(2026, 7, 6), date(2026, 7, 12), "Energize critical distribution", 6),
    "T-180": (date(2026, 7, 13), date(2026, 7, 21), "Integrated systems test", 6),
}

# Dates lost to weather, with the condition recorded that day. A pre-monsoon
# thunderstorm sequence in late May, then monsoon onset from late June.
LOST = {
    date(2026, 5, 12): "thunderstorm — crane lifts suspended",
    date(2026, 5, 13): "thunderstorm — crane lifts suspended",
    date(2026, 6, 1): "heavy rain — external works stopped",
    date(2026, 6, 26): "monsoon onset — site access flooded",
    date(2026, 6, 29): "monsoon rain — external works stopped",
    date(2026, 6, 30): "monsoon rain — external works stopped",
    date(2026, 7, 1): "monsoon rain — roof penetrations deferred",
    date(2026, 7, 7): "monsoon rain — switchroom humidity above limit",
    date(2026, 7, 8): "monsoon rain — switchroom humidity above limit",
    date(2026, 7, 15): "monsoon rain — external works stopped",
}

# Crew shortfalls, by date: (absent, reason). Everything else is fully manned.
ABSENCE = {
    date(2026, 5, 6): (2, "certified electricians reassigned to another synthetic site"),
    date(2026, 5, 7): (2, "certified electricians reassigned to another synthetic site"),
    date(2026, 5, 20): (1, "reported sick"),
    date(2026, 6, 3): (1, "reported sick"),
    date(2026, 6, 4): (1, "vendor technician travel delay"),
    date(2026, 7, 9): (2, "commissioning engineer shortage"),
    date(2026, 7, 10): (2, "commissioning engineer shortage"),
}

FAIR = "fair — no weather restriction"


def rows():
    for task_id, (start, finish, task_name, crew) in WINDOWS.items():
        day = start
        while day <= finish:
            if day.weekday() >= 5:  # the synthetic site does not work weekends
                day += timedelta(days=1)
                continue
            lost = day in LOST
            absent, reason = ABSENCE.get(day, (0, ""))
            present = 0 if lost else max(0, crew - absent)
            yield {
                "project_id": PROJECT,
                "data_classification": CLASSIFICATION,
                "record_date": day.isoformat(),
                "task_id": task_id,
                "task_name": task_name,
                "weather_condition": LOST.get(day, FAIR),
                "lost_workday": "true" if lost else "false",
                "planned_crew": crew,
                "present_crew": present,
                "absence_reason": "weather stand-down" if lost else reason,
                "notes": "Synthetic daily site record.",
            }
            day += timedelta(days=1)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = list(rows())
    with OUT.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)

    lost_by_task, planned, present = {}, 0, 0
    for record in records:
        planned += record["planned_crew"]
        present += record["present_crew"]
        if record["lost_workday"] == "true":
            lost_by_task[record["task_id"]] = lost_by_task.get(record["task_id"], 0) + 1
    print(f"{OUT.relative_to(ROOT)}: {len(records)} rows")
    print(f"weather-lost days by task : {lost_by_task}")
    print(f"crew-days present/planned : {present}/{planned} = {present / planned:.4f}")


if __name__ == "__main__":
    main()
