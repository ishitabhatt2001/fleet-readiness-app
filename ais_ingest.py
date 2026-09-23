"""
Naval Fleet Readiness & Maintenance Intelligence Platform
Real-time AIS ingestion for Indian coastal waters, via aisstream.io.

WHAT THIS DOES
    Connects to the free aisstream.io WebSocket feed, subscribes to a bounding
    box covering the Indian coastline (Arabian Sea + Bay of Bengal), and
    appends every position report it receives to a CSV file - in the same
    shape as the fact_vessel_positions table in sql/schema.sql.

SETUP
    1. pip install websockets python-dotenv
    2. Create a .env file in this folder with:
           AISSTREAM_API_KEY=your_key_here
    3. Run it:
           python ais_ingest.py
    4. Leave it running in a terminal for a few hours (or overnight) to
       collect a meaningful number of position reports. Press Ctrl+C to stop
       - the CSV is flushed after every message, so nothing is lost.

OUTPUT
    data/output/fact_vessel_positions.csv
    Columns: vessel_id, name, vessel_type, timestamp, lat, lon, speed_knots, heading_deg

NOTES
    - vessel_id here is the MMSI (Maritime Mobile Service Identifier) - the
      standard unique ID broadcast by every AIS-equipped ship. Use it as the
      vessel_id / primary key when you load this into dim_vessel /
      fact_vessel_positions.
    - "name" and "vessel_type" often arrive empty on the first few messages
      for a given ship - AIS static data (name, type) is broadcast less
      frequently than position reports. The script fills them in as soon as
      that data arrives and back-fills nothing retroactively; that's fine for
      a portfolio dataset.
    - This is real, live data - no synthetic-data caveat needed for this file.
      Keep using generate_maintenance_data.py for the maintenance/readiness
      side, since those records aren't public for any fleet.
"""

import asyncio
import csv
import os
import json
from datetime import datetime, timezone

import websockets
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AISSTREAM_API_KEY")
if not API_KEY:
    raise SystemExit(
        "Missing AISSTREAM_API_KEY. Create a .env file with:\n"
        "AISSTREAM_API_KEY=your_key_here"
    )

# Bounding box covering the Indian coastline: Arabian Sea + Bay of Bengal
# Format per aisstream.io spec: [[min_lat, min_lon], [max_lat, max_lon]]
INDIA_BOUNDING_BOX = [[6.0, 68.0], [24.0, 93.0]]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "fact_vessel_positions.csv")

FIELDNAMES = ["vessel_id", "name", "vessel_type", "timestamp", "lat", "lon", "speed_knots", "heading_deg"]

# Keep light in-memory cache of ship names/types as they arrive via ShipStaticData messages,
# so position rows can be enriched even though the two message types arrive separately.
ship_info_cache = {}


def ensure_csv_header():
    if not os.path.exists(OUTPUT_PATH) or os.path.getsize(OUTPUT_PATH) == 0:
        with open(OUTPUT_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()


def append_row(row: dict):
    with open(OUTPUT_PATH, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)


async def connect_ais_stream():
    ensure_csv_header()
    message_count = 0

    async with websockets.connect("wss://stream.aisstream.io/v0/stream") as websocket:
        subscribe_message = {
            "APIKey": API_KEY,
            "BoundingBoxes": [INDIA_BOUNDING_BOX],
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        }
        await websocket.send(json.dumps(subscribe_message))
        print(f"Subscribed to Indian coastal waters {INDIA_BOUNDING_BOX}")
        print(f"Writing to {OUTPUT_PATH}")
        print("Press Ctrl+C to stop.\n")

        async for raw_message in websocket:
            message = json.loads(raw_message)
            msg_type = message.get("MessageType")
            metadata = message.get("MetaData", {})
            mmsi = str(metadata.get("MMSI", ""))

            if msg_type == "ShipStaticData":
                data = message["Message"]["ShipStaticData"]
                ship_info_cache[mmsi] = {
                    "name": data.get("ShipName", "").strip(),
                    "vessel_type": data.get("Type", "Unknown"),
                }

            elif msg_type == "PositionReport":
                data = message["Message"]["PositionReport"]
                info = ship_info_cache.get(mmsi, {})
                row = {
                    "vessel_id": mmsi,
                    "name": info.get("name", ""),
                    "vessel_type": info.get("vessel_type", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "lat": data.get("Latitude"),
                    "lon": data.get("Longitude"),
                    "speed_knots": data.get("Sog"),   # Speed Over Ground
                    "heading_deg": data.get("TrueHeading"),
                }
                append_row(row)
                message_count += 1
                if message_count % 25 == 0:
                    print(f"  ...{message_count} position reports saved")


if __name__ == "__main__":
    try:
        asyncio.run(connect_ais_stream())
    except KeyboardInterrupt:
        print("\nStopped. Data saved to", OUTPUT_PATH)