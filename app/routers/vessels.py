"""
Vessel endpoints - now backed by the real Postgres/Supabase database instead
of the earlier hardcoded MOCK_VESSELS list.

Reads from fact_vessel_positions (joined to dim_vessel for name/vessel_type),
loaded there by load_to_postgres.py from your collected AIS data.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from app.db import get_cursor

router = APIRouter()


class VesselPosition(BaseModel):
    vessel_id: str
    name: str | None = None
    vessel_type: str | None = None
    lat: float
    lon: float
    speed_knots: float | None = None
    heading_deg: float | None = None
    timestamp: datetime


# Returns each vessel's SINGLE latest position (not full history) - this is
# the "latest position per vessel" pattern the build guide's live-view
# section calls for, using PostgreSQL's DISTINCT ON.
LATEST_POSITIONS_SQL = """
    SELECT DISTINCT ON (p.vessel_id)
        p.vessel_id,
        v.name,
        v.vessel_type,
        p.lat,
        p.lon,
        p.speed_knots,
        p.heading_deg,
        p."timestamp"
    FROM fact_vessel_positions p
    LEFT JOIN dim_vessel v ON v.vessel_id = p.vessel_id
    ORDER BY p.vessel_id, p."timestamp" DESC
"""


@router.get("/", response_model=list[VesselPosition])
def list_vessels():
    """Return the latest known position for every vessel in the database."""
    with get_cursor() as cur:
        cur.execute(LATEST_POSITIONS_SQL)
        return cur.fetchall()


SINGLE_VESSEL_LATEST_SQL = """
    SELECT DISTINCT ON (p.vessel_id)
        p.vessel_id,
        v.name,
        v.vessel_type,
        p.lat,
        p.lon,
        p.speed_knots,
        p.heading_deg,
        p."timestamp"
    FROM fact_vessel_positions p
    LEFT JOIN dim_vessel v ON v.vessel_id = p.vessel_id
    WHERE p.vessel_id = %s
    ORDER BY p.vessel_id, p."timestamp" DESC
"""


@router.get("/{vessel_id}", response_model=VesselPosition)
def get_vessel(vessel_id: str):
    """Return the latest position for a single vessel by ID (MMSI)."""
    with get_cursor() as cur:
        cur.execute(SINGLE_VESSEL_LATEST_SQL, (vessel_id,))
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No position data found for vessel_id={vessel_id}")
        return row


@router.get("/{vessel_id}/history", response_model=list[VesselPosition])
def get_vessel_history(vessel_id: str, limit: int = 100):
    """Return recent position history for a single vessel (for plotting a track)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT p.vessel_id, v.name, v.vessel_type, p.lat, p.lon,
                   p.speed_knots, p.heading_deg, p."timestamp"
            FROM fact_vessel_positions p
            LEFT JOIN dim_vessel v ON v.vessel_id = p.vessel_id
            WHERE p.vessel_id = %s
            ORDER BY p."timestamp" DESC
            LIMIT %s
            """,
            (vessel_id, limit),
        )
        return cur.fetchall()
