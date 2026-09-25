"""
Generates a realistic SIMULATED fleet maintenance dataset as CSV files,
matching the star schema in sql/schema.sql.

This data is entirely synthetic - it does not represent any real fleet,
vessel, or maintenance record. It is generated AGAINST THE REAL VESSEL IDs
(MMSIs) already collected in data/output/fact_vessel_positions.csv via
ingest.py, so a ship that's real in your position data also gets
(simulated) maintenance and readiness history - letting them join cleanly
in Postgres and in LLM queries.

Usage:
    1. Run ingest.py first and collect some AIS data (fact_vessel_positions.csv
       must already exist in data/output/).
    2. pip install -r requirements.txt
    3. python data/generate_maintenance_data.py
Outputs dim_vessel.csv, fact_maintenance_events.csv, fact_readiness_status.csv
into data/output/.
"""

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
POSITIONS_CSV = os.path.join(OUTPUT_DIR, "fact_vessel_positions.csv")
os.makedirs(OUTPUT_DIR, exist_ok=True)

VESSEL_TYPES = ["Frigate", "Destroyer", "Corvette", "Submarine", "Patrol Vessel"]
EQUIPMENT_TYPES = ["Propulsion", "Radar", "Engine", "Sonar", "Communications", "Weapons System"]
EVENT_TYPES = ["scheduled", "unscheduled", "inspection"]
BASES = ["Eastern Naval Command", "Western Naval Command", "Southern Naval Command"]

N_MAINTENANCE_EVENTS_PER_VESSEL = 5   # avg maintenance events to generate per real vessel
N_READINESS_DAYS = 30                 # trailing days of readiness snapshots


def load_real_vessels():
    """
    Read the distinct vessel_id (MMSI), name, and vessel_type values already
    collected by ingest.py, so the synthetic maintenance/readiness data lines
    up with the real ships in fact_vessel_positions.csv.
    """
    if not os.path.exists(POSITIONS_CSV):
        raise SystemExit(
            f"Could not find {POSITIONS_CSV}.\n"
            "Run ingest.py first and let it collect some AIS data, then re-run this script."
        )

    vessels = {}
    with open(POSITIONS_CSV, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            vid = row.get("vessel_id", "").strip()
            if not vid:
                continue
            # Keep the first non-empty name/vessel_type seen for each vessel;
            # AIS static data (name/type) doesn't arrive with every row.
            if vid not in vessels:
                vessels[vid] = {"vessel_id": vid, "name": "", "vessel_type": ""}
            if not vessels[vid]["name"] and row.get("name", "").strip():
                vessels[vid]["name"] = row["name"].strip()
            if not vessels[vid]["vessel_type"] and row.get("vessel_type", "").strip():
                vessels[vid]["vessel_type"] = row["vessel_type"].strip()

    if not vessels:
        raise SystemExit(f"{POSITIONS_CSV} exists but contains no vessel rows yet.")

    # Fill in any still-blank name/type with a plausible placeholder so the
    # dataset is complete and readable, and attach a random home base.
    result = []
    for i, v in enumerate(vessels.values(), start=1):
        result.append({
            "vessel_id": v["vessel_id"],
            "name": v["name"] or f"Vessel-{i:03d}",
            "vessel_type": v["vessel_type"] or random.choice(VESSEL_TYPES),
            "base_name": random.choice(BASES),
        })

    print(f"Loaded {len(result)} real vessel(s) (MMSIs) from {POSITIONS_CSV}")
    return result


def generate_maintenance_events(vessels):
    events = []
    for vessel in vessels:
        n_events = random.randint(2, N_MAINTENANCE_EVENTS_PER_VESSEL)
        for _ in range(n_events):
            event_date = date.today() - timedelta(days=random.randint(0, 180))
            events.append({
                "vessel_id": vessel["vessel_id"],
                "equipment_type": random.choice(EQUIPMENT_TYPES),
                "event_date": event_date.isoformat(),
                "downtime_hrs": round(random.uniform(0.5, 48.0), 1),
                "event_type": random.choice(EVENT_TYPES),
            })
    return events


def generate_readiness(vessels):
    rows = []
    for vessel in vessels:
        score = random.uniform(60, 100)
        for d in range(N_READINESS_DAYS):
            day = date.today() - timedelta(days=d)
            # small daily drift so it looks like a real time series
            score = max(30, min(100, score + random.uniform(-4, 3)))
            status = "ready" if score >= 80 else "limited" if score >= 50 else "unavailable"
            rows.append({
                "vessel_id": vessel["vessel_id"],
                "date": day.isoformat(),
                "readiness_score": round(score, 1),
                "status": status,
            })
    return rows


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path}")


if __name__ == "__main__":
    vessels = load_real_vessels()
    events = generate_maintenance_events(vessels)
    readiness = generate_readiness(vessels)

    write_csv(os.path.join(OUTPUT_DIR, "dim_vessel.csv"), vessels,
              ["vessel_id", "name", "vessel_type", "base_name"])
    write_csv(os.path.join(OUTPUT_DIR, "fact_maintenance_events.csv"), events,
              ["vessel_id", "equipment_type", "event_date", "downtime_hrs", "event_type"])
    write_csv(os.path.join(OUTPUT_DIR, "fact_readiness_status.csv"), readiness,
              ["vessel_id", "date", "readiness_score", "status"])

    print("\nDone. Maintenance/readiness data is SIMULATED for portfolio/demo purposes only.")
    print("Vessel IDs (MMSIs) are real, collected via ingest.py from AISstream.io.")