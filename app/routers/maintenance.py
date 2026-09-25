"""
Maintenance + readiness endpoints - now backed by the real Postgres/Supabase
database instead of the earlier hardcoded MOCK_MAINTENANCE / MOCK_READINESS
lists.

Reads from fact_maintenance_events / fact_readiness_status, loaded there by
load_to_postgres.py from data/generate_maintenance_data.py's output.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date

from app.db import get_cursor

router = APIRouter()


class MaintenanceEvent(BaseModel):
    vessel_id: str
    equipment_type: str | None = None
    event_date: date
    downtime_hrs: float | None = None
    event_type: str | None = None


class ReadinessStatus(BaseModel):
    vessel_id: str
    date: date
    readiness_score: float | None = None
    status: str | None = None


@router.get("/events", response_model=list[MaintenanceEvent])
def list_maintenance_events(limit: int = 100):
    """Return recent maintenance events across the fleet, most recent first."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT m.vessel_id, e.equipment_type, m.event_date, m.downtime_hrs, m.event_type
            FROM fact_maintenance_events m
            LEFT JOIN dim_equipment e ON e.equipment_id = m.equipment_id
            ORDER BY m.event_date DESC
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


@router.get("/readiness", response_model=list[ReadinessStatus])
def list_readiness():
    """Return each vessel's most recent readiness snapshot."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (vessel_id)
                vessel_id, date, readiness_score, status
            FROM fact_readiness_status
            ORDER BY vessel_id, date DESC
            """
        )
        return cur.fetchall()


@router.get("/readiness/{vessel_id}", response_model=ReadinessStatus)
def get_readiness(vessel_id: str):
    """Return the most recent readiness snapshot for a single vessel."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT vessel_id, date, readiness_score, status
            FROM fact_readiness_status
            WHERE vessel_id = %s
            ORDER BY date DESC
            LIMIT 1
            """,
            (vessel_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"No readiness data found for vessel_id={vessel_id}")
        return row


@router.get("/readiness/{vessel_id}/history", response_model=list[ReadinessStatus])
def get_readiness_history(vessel_id: str, days: int = 30):
    """Return readiness history for a single vessel (for a trend chart)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT vessel_id, date, readiness_score, status
            FROM fact_readiness_status
            WHERE vessel_id = %s
            ORDER BY date DESC
            LIMIT %s
            """,
            (vessel_id, days),
        )
        return cur.fetchall()
