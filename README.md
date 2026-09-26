# Naval Fleet Readiness & Maintenance Intelligence Platform

An end-to-end portfolio project combining AWS, data modeling, containers, VM
provisioning/maintenance, and LLM integration around a naval fleet-tracking
domain.

**Data:** real vessel-position data collected live via [AISstream.io](https://aistream.io)
(global, real-time AIS WebSocket feed — used instead of NOAA AIS to cover
Indian coastal waters) + simulated fleet maintenance/readiness data
(clearly labeled as synthetic, generated against the same real vessel IDs
so the two data sets line up).

This repo covers **local development through a working, database-backed
FastAPI backend + Streamlit frontend with a live LLM query layer** — built
and verified locally in VS Code, wrapped in Docker, pushed to GitHub, and
ready to deploy to a low-cost AWS slice in the next stage of the build guide.

## Current status

- ✅ Real AIS ingestion (`ais_ingest.py`) pulling live vessel positions from
  AISstream.io
- ✅ Synthetic maintenance/readiness data generated against the same real
  vessel IDs (`data/generate_maintenance_data.py`)
- ✅ Star-schema Postgres database on Supabase (`sql/schema.sql`), loaded via
  `load_to_postgres.py`
- ✅ FastAPI backend fully wired to Postgres — no more mock data:
  - `vessels.py` — latest position per vessel (`DISTINCT ON`) + `/vessels/{id}/history`
  - `maintenance.py` — recent maintenance events, current readiness per
    vessel, and `/readiness/{id}/history`
- ✅ Streamlit dashboard — vessel positions map, maintenance/readiness views,
  natural-language "Ask a Question" tab
- ✅ Live LLM query layer (`app/routers/query.py`) using Groq's free-tier API
  (`openai/gpt-oss-20b`) — pulls a compact live-fleet-state summary from
  Postgres as context, so questions are answered grounded in real data
- ✅ Supabase Row Level Security enabled with public-read policies
- ⬜ Deployed to AWS (next stage — thin, low-cost slice per the build guide)

## Project structure

```
fleet-readiness-app/
├── app/                        # FastAPI backend
│   ├── main.py                 # app entrypoint
│   ├── db.py                   # shared Postgres/Supabase connection pool
│   └── routers/
│       ├── vessels.py          # vessel position endpoints (real Postgres data)
│       ├── maintenance.py      # maintenance + readiness endpoints (real Postgres data)
│       └── query.py            # LLM natural-language query layer (Groq)
├── frontend/
│   └── streamlit_app.py        # dashboard: positions, maintenance, ask-a-question
├── data/
│   └── generate_maintenance_data.py   # synthetic data generator -> CSVs
├── sql/
│   └── schema.sql              # star schema (fact + dimension tables)
├── .github/workflows/
│   └── deploy.yml              # CI/CD stub for the AWS deployment stage
├── ais_ingest.py                # live AIS ingestion from AISstream.io
├── load_to_postgres.py          # loads generated + ingested data into Supabase
├── Dockerfile                  # backend image
├── Dockerfile.frontend         # frontend image
├── docker-compose.yml          # run both together locally
├── requirements.txt
├── .env.example
└── .vscode/                    # launch config + recommended extensions
```

## 1. Run locally in VS Code (no Docker)

```
# from the project root
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in DATABASE_URL, GROQ_API_KEY, AISSTREAM_API_KEY

# terminal 1: backend
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
streamlit run frontend/streamlit_app.py
```

- Backend docs: <http://localhost:8000/docs>
- Dashboard: <http://localhost:8501>

Open the folder in VS Code, select the `.venv` interpreter (Python:
Select Interpreter), and use the run configs in `.vscode/launch.json` if you
prefer the debugger over the terminal.

## 2. Run with Docker

```
docker build -t fleet-readiness-app .
docker run -p 8000:8000 --env-file .env fleet-readiness-app
```

Or run backend + frontend together:

```
docker compose up --build
```

## 3. Collect real AIS data

```
python ais_ingest.py
```

Streams live vessel positions from AISstream.io and writes them out for
loading into Postgres.

## 4. Generate synthetic maintenance data

```
python data/generate_maintenance_data.py
```

Writes CSVs to `data/output/`, generated against the same vessel IDs
collected by `ais_ingest.py` so real position data and simulated
maintenance data line up. This is **simulated data only** — real naval
maintenance records aren't public; this is standard practice for
portfolio projects, just keep it labeled as simulated.

## 5. Load everything into Postgres / Supabase

```
psql "$DATABASE_URL" -f sql/schema.sql
python load_to_postgres.py
```

## Next steps (remaining stage of the build guide)

- Provision an EC2 VM (or equivalent low-cost slice), install Docker, and
  deploy — manual pull or the GitHub Actions workflow stub in
  `.github/workflows/deploy.yml`
- Point the dashboard at the deployed backend URL and share the live link

## Notes

- The maintenance/readiness data is **synthetic** — real naval maintenance
  records aren't public. This is standard practice for portfolio projects;
  just keep it labeled as simulated.
- Vessel position data comes from AISstream.io's live global AIS feed.