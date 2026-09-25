"""
Naval Fleet Readiness & Maintenance Intelligence Platform
FastAPI backend entrypoint.

Run locally:
    uvicorn app.main:app --reload --port 8000

Run in Docker:
    docker build -t fleet-readiness-app .
    docker run -p 8000:8000 fleet-readiness-app
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import vessels, maintenance, query

app = FastAPI(
    title="Naval Fleet Readiness & Maintenance Intelligence API",
    description=(
        "Backend for the Naval Fleet Readiness & Maintenance Intelligence Platform. "
        "Serves vessel position data (AIS), simulated maintenance data, and an "
        "LLM-powered natural-language query layer over both."
    ),
    version="0.1.0",
)

# Allow the Streamlit frontend (running on a different port/container) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vessels.router, prefix="/vessels", tags=["vessels"])
app.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])
app.include_router(query.router, prefix="/query", tags=["llm-query"])


@app.get("/")
def root():
    return {
        "service": "fleet-readiness-api",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    """Basic health check endpoint - useful once this is deployed on the EC2 VM."""
    return {"status": "healthy"}
