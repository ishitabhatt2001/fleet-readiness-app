"""
Naval Fleet Readiness & Maintenance Intelligence Platform
Loads the collected/generated CSVs into your Postgres (Supabase) database,
matching the star schema in sql/schema.sql.

PREREQUISITES
    1. sql/schema.sql has already been applied to your database:
           psql "$DATABASE_URL" -f sql/schema.sql
       (or run it via the Supabase SQL editor)
    2. .env contains DATABASE_URL, e.g.:
           DATABASE_URL=postgresql://user:password@host:5432/dbname
    3. These four CSVs exist in data/output/ (from ingest.py and
       generate_maintenance_data.py):
           fact_vessel_positions.csv
           dim_vessel.csv
           fact_maintenance_events.csv
           fact_readiness_status.csv

USAGE
    pip install psycopg2-binary python-dotenv
    python load_to_postgres.py

This script is safe to re-run: dim_vessel rows are upserted (ON CONFLICT
DO UPDATE), and fact tables are appended - so running it again after
collecting more AIS data or regenerating maintenance data just adds the
new rows rather than duplicating everything blindly. If you want a clean
reload instead, pass --truncate.

psql "$env:DATABASE_URL" -f sql/schema.sql
"""

import csv
import os
import sys
import argparse

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "Missing DATABASE_URL. Add it to your .env file, e.g.:\n"
        "DATABASE_URL=postgresql://user:password@host:5432/dbname"
    )

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "output")

DIM_VESSEL_CSV = os.path.join(DATA_DIR, "dim_vessel.csv")
POSITIONS_CSV = os.path.join(DATA_DIR, "fact_vessel_positions.csv")
MAINTENANCE_CSV = os.path.join(DATA_DIR, "fact_maintenance_events.csv")
READINESS_CSV = os.path.join(DATA_DIR, "fact_readiness_status.csv")


def read_csv(path):
    if not os.path.exists(path):
        print(f"  [skip] {path} not found")
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def none_if_blank(value):
    return value if value not in ("", None) else None


def load_dim_vessel(conn, rows):
    if not rows:
        return
    # dim_vessel.base_id is a foreign key to dim_base, but generate_maintenance_data.py
    # only gives us a base_name. Upsert distinct bases first, then look up their IDs.
    base_names = sorted({r["base_name"] for r in rows if r.get("base_name")})
    with conn.cursor() as cur:
        base_id_by_name = {}
        for name in base_names:
            # dim_base.base_name has no unique constraint in schema.sql, so we
            # look it up first rather than relying on ON CONFLICT - avoids
            # creating duplicate base rows if this script is run more than once.
            cur.execute("SELECT base_id FROM dim_base WHERE base_name = %s", (name,))
            result = cur.fetchone()
            if result is None:
                cur.execute(
                    "INSERT INTO dim_base (base_name) VALUES (%s) RETURNING base_id",
                    (name,),
                )
                result = cur.fetchone()
            base_id_by_name[name] = result[0]

        values = [
            (
                r["vessel_id"],
                r["name"],
                r["vessel_type"],
                base_id_by_name.get(r.get("base_name")),
            )
            for r in rows
        ]
        execute_values(
            cur,
            """
            INSERT INTO dim_vessel (vessel_id, name, vessel_type, base_id)
            VALUES %s
            ON CONFLICT (vessel_id) DO UPDATE SET
                name = EXCLUDED.name,
                vessel_type = EXCLUDED.vessel_type,
                base_id = EXCLUDED.base_id
            """,
            values,
        )
    conn.commit()
    print(f"  Upserted {len(rows)} rows -> dim_vessel ({len(base_names)} bases)")


def load_fact_vessel_positions(conn, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        values = [
            (
                r["vessel_id"],
                r["timestamp"],
                float(r["lat"]) if r.get("lat") else None,
                float(r["lon"]) if r.get("lon") else None,
                float(r["speed_knots"]) if r.get("speed_knots") else None,
                float(r["heading_deg"]) if r.get("heading_deg") else None,
            )
            for r in rows
            if r.get("lat") and r.get("lon")  # skip incomplete rows
        ]
        execute_values(
            cur,
            """
            INSERT INTO fact_vessel_positions
                (vessel_id, "timestamp", lat, lon, speed_knots, heading_deg)
            VALUES %s
            """,
            values,
        )
    conn.commit()
    print(f"  Inserted {len(values)} rows -> fact_vessel_positions")


def load_fact_maintenance_events(conn, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        # equipment_id is a foreign key to dim_equipment; upsert distinct
        # equipment_types first, then map event rows to their equipment_id.
        equipment_types = sorted({r["equipment_type"] for r in rows if r.get("equipment_type")})
        equipment_id_by_type = {}
        for etype in equipment_types:
            cur.execute("SELECT equipment_id FROM dim_equipment WHERE equipment_type = %s", (etype,))
            result = cur.fetchone()
            if result is None:
                cur.execute(
                    "INSERT INTO dim_equipment (equipment_type) VALUES (%s) RETURNING equipment_id",
                    (etype,),
                )
                result = cur.fetchone()
            equipment_id_by_type[etype] = result[0]

        values = [
            (
                r["vessel_id"],
                equipment_id_by_type.get(r.get("equipment_type")),
                r["event_date"],
                float(r["downtime_hrs"]) if r.get("downtime_hrs") else None,
                r.get("event_type"),
            )
            for r in rows
        ]
        execute_values(
            cur,
            """
            INSERT INTO fact_maintenance_events
                (vessel_id, equipment_id, event_date, downtime_hrs, event_type)
            VALUES %s
            """,
            values,
        )
    conn.commit()
    print(f"  Inserted {len(values)} rows -> fact_maintenance_events ({len(equipment_types)} equipment types)")


def load_fact_readiness_status(conn, rows):
    if not rows:
        return
    with conn.cursor() as cur:
        values = [
            (
                r["vessel_id"],
                r["date"],
                float(r["readiness_score"]) if r.get("readiness_score") else None,
                r.get("status"),
            )
            for r in rows
        ]
        execute_values(
            cur,
            """
            INSERT INTO fact_readiness_status (vessel_id, date, readiness_score, status)
            VALUES %s
            """,
            values,
        )
    conn.commit()
    print(f"  Inserted {len(values)} rows -> fact_readiness_status")


def truncate_all(conn):
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE fact_vessel_positions, fact_maintenance_events, "
            "fact_readiness_status, dim_vessel, dim_equipment, dim_base RESTART IDENTITY CASCADE"
        )
    conn.commit()
    print("Truncated all tables before reload.\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--truncate", action="store_true",
        help="Clear all tables before loading, instead of upserting/appending.",
    )
    args = parser.parse_args()

    print(f"Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)

    try:
        if args.truncate:
            truncate_all(conn)

        print("Loading dim_vessel.csv ...")
        load_dim_vessel(conn, read_csv(DIM_VESSEL_CSV))

        print("Loading fact_vessel_positions.csv ...")
        load_fact_vessel_positions(conn, read_csv(POSITIONS_CSV))

        print("Loading fact_maintenance_events.csv ...")
        load_fact_maintenance_events(conn, read_csv(MAINTENANCE_CSV))

        print("Loading fact_readiness_status.csv ...")
        load_fact_readiness_status(conn, read_csv(READINESS_CSV))

        print("\nDone. All available CSVs loaded into Postgres.")
    except Exception as e:
        conn.rollback()
        print(f"\nError during load, rolled back this table's changes: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
