"""
LLM query layer - now wired up to a real provider (Groq, free tier).

Approach: rather than having the LLM generate raw SQL to execute directly
(riskier - a wrong query could error out or, worse, do something unintended),
this pulls a compact summary of the current fleet data from Postgres and
hands that to the LLM as context, asking it to answer the question in plain
English. This is the simpler, safer pattern for a demo/portfolio project and
still fully demonstrates NL-over-data querying.

SETUP
    1. Sign up free at https://console.groq.com -> API Keys -> create one
    2. Add to .env:
           GROQ_API_KEY=your_key_here
    3. pip install groq
"""

import os
from fastapi import APIRouter
from pydantic import BaseModel
from groq import Groq

from app.db import get_cursor

router = APIRouter()

GROQ_MODEL = "openai/gpt-oss-20b"  # Groq deprecated llama-3.1-8b-instant on 08/16/26; this is their recommended replacement

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        _client = Groq(api_key=api_key)
    return _client


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    answer: str
    used_llm: bool


def build_fleet_context() -> str:
    """
    Pulls a compact snapshot of the fleet's current state from Postgres -
    latest position, latest readiness, and recent maintenance events per
    vessel - and formats it as plain text for the LLM's system prompt.

    Kept intentionally small (one row per vessel + recent events only) so it
    fits comfortably in context and keeps token usage low on the free tier.
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (p.vessel_id)
                p.vessel_id, v.name, v.vessel_type, p.lat, p.lon,
                p.speed_knots, p."timestamp"
            FROM fact_vessel_positions p
            LEFT JOIN dim_vessel v ON v.vessel_id = p.vessel_id
            ORDER BY p.vessel_id, p."timestamp" DESC
            """
        )
        positions = cur.fetchall()

        cur.execute(
            """
            SELECT DISTINCT ON (vessel_id)
                vessel_id, date, readiness_score, status
            FROM fact_readiness_status
            ORDER BY vessel_id, date DESC
            """
        )
        readiness = {r["vessel_id"]: r for r in cur.fetchall()}

        cur.execute(
            """
            SELECT m.vessel_id, e.equipment_type, m.event_date, m.downtime_hrs, m.event_type
            FROM fact_maintenance_events m
            LEFT JOIN dim_equipment e ON e.equipment_id = m.equipment_id
            ORDER BY m.event_date DESC
            LIMIT 50
            """
        )
        events_by_vessel = {}
        for e in cur.fetchall():
            events_by_vessel.setdefault(e["vessel_id"], []).append(e)

    lines = ["Current fleet snapshot:\n"]
    for p in positions:
        vid = p["vessel_id"]
        r = readiness.get(vid)
        name = p.get("name") or "Unknown"
        vtype = p.get("vessel_type") or "Unknown type"
        line = (
            f"- Vessel {vid} ({name}, {vtype}): "
            f"position ({p['lat']:.3f}, {p['lon']:.3f}), "
            f"speed {p.get('speed_knots') or 0:.1f} kn, "
            f"last seen {p['timestamp']}"
        )
        if r:
            line += f"; readiness {r['readiness_score']} ({r['status']}) as of {r['date']}"
        vessel_events = events_by_vessel.get(vid, [])[:3]
        if vessel_events:
            ev_summary = "; ".join(
                f"{ev['event_type']} on {ev['equipment_type']} ({ev['event_date']}, {ev['downtime_hrs']}h downtime)"
                for ev in vessel_events
            )
            line += f"; recent maintenance: {ev_summary}"
        lines.append(line)

    return "\n".join(lines)


SYSTEM_PROMPT_TEMPLATE = """You are a fleet readiness analyst assistant for a naval fleet tracking \
platform. Answer questions using ONLY the fleet data provided below. Be \
concise and specific - cite vessel IDs/names when relevant. If the data \
doesn't contain enough information to answer, say so rather than guessing.

{fleet_context}
"""


def call_llm(question: str) -> str:
    client = get_client()
    if client is None:
        return (
            "[Stub response - no LLM API key set] "
            f"You asked: '{question}'. Add GROQ_API_KEY to your .env file to get a real answer."
        )

    fleet_context = build_fleet_context()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(fleet_context=fleet_context)

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.2,
        max_tokens=800,
        reasoning_effort="low",  # gpt-oss-20b is a reasoning model - "low" leaves more
                                 # of the token budget for the actual answer instead of
                                 # internal reasoning tokens, which were previously
                                 # exhausting max_tokens before any content was written.
    )
    message = response.choices[0].message
    content = (message.content or "").strip()
    if not content:
        # Fallback: if content still came back empty (e.g. cut off), surface the
        # reasoning trace so the user at least sees something instead of blank.
        reasoning = getattr(message, "reasoning", None)
        if reasoning:
            content = f"[Model's reasoning, final answer was empty - try increasing max_tokens]\n\n{reasoning}"
        else:
            content = "The model returned an empty response. Try rephrasing the question or increasing max_tokens in query.py."
    return content


@router.post("/", response_model=QueryResponse)
def ask_question(payload: QueryRequest):
    """Ask a natural-language question about fleet readiness/maintenance."""
    answer = call_llm(payload.question)
    return QueryResponse(
        question=payload.question,
        answer=answer,
        used_llm=bool(os.getenv("GROQ_API_KEY")),
    )