# Naval Fleet Readiness & Maintenance Intelligence Platform

An end-to-end portfolio project combining AWS, data modeling, containers, VM
provisioning/maintenance, and LLM integration around a naval fleet-tracking
domain.

**Data:** real public NOAA AIS vessel-position data + simulated fleet
maintenance/readiness data (clearly labeled as synthetic).

This repo covers **Step 1 - Local Development** of the build guide: a working
FastAPI backend + Streamlit frontend you can run locally in VS Code, wrapped
in Docker, ready to push to GitHub and deploy to an EC2 VM in later steps.

## Project structure

```
fleet-readiness-app/
├── app/                        # FastAPI backend
│   ├── main.py                 # app entrypoint
│   └── routers/
│       ├── vessels.py          # vessel position endpoints (mock AIS data)
│       ├── maintenance.py      # maintenance + readiness endpoints (mock data)
│       └── query.py            # LLM natural-language query layer (stub)
├── frontend/
│   └── streamlit_app.py        # dashboard: positions, maintenance, ask-a-question
├── data/
│   └── generate_maintenance_data.py   # synthetic data generator -> CSVs
├── sql/
│   └── schema.sql              # star schema (fact + dimension tables)
├── .github/workflows/
│   └── deploy.yml              # CI/CD stub for later (Step 4B in the guide)
├── Dockerfile                  # backend image
├── Dockerfile.frontend         # frontend image
├── docker-compose.yml          # run both together locally
├── requirements.txt
├── .env.example
└── .vscode/                    # launch config + recommended extensions
```

## 1. Run locally in VS Code (no Docker)

```bash
# from the project root
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env             # fill in values later - not required yet

# terminal 1: backend
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend
streamlit run frontend/streamlit_app.py
```

- Backend docs: http://localhost:8000/docs
- Dashboard: http://localhost:8501

Both routers currently return **mock data** so the whole app runs with zero
setup. Swap the mock lists in `vessels.py` / `maintenance.py` for real
Postgres queries once your database is populated (see `sql/schema.sql` and
`data/generate_maintenance_data.py`).

Open the folder in VS Code, select the `.venv` interpreter (Python:
Select Interpreter), and use the run configs in `.vscode/launch.json` if you
prefer the debugger over the terminal.

## 2. Run with Docker (matches the guide's "verify the image runs" step)

```bash
docker build -t fleet-readiness-app .
docker run -p 8000:8000 fleet-readiness-app
```

Or run backend + frontend together:

```bash
docker compose up --build
```

## 3. Generate synthetic maintenance data

```bash
python data/generate_maintenance_data.py
```

Writes CSVs to `data/output/`. This is **simulated data only** - pair it with
real AIS data from [MarineCadastre.gov](https://marinecadastre.gov/ais/) for
the vessel-position side of the project.

## 4. Load the schema into Postgres / Supabase

```bash
psql "$DATABASE_URL" -f sql/schema.sql
```

## Next steps (later stages of the build guide)

- Push this repo to GitHub (`.gitignore` already excludes `.env` and secrets)
- Provision an EC2 VM, install Docker, and deploy (manual pull or the
  GitHub Actions workflow stub in `.github/workflows/deploy.yml`)
- Wire up a real LLM provider (Groq or AWS Bedrock free tier) in
  `app/routers/query.py`
- Point `vessels.py` / `maintenance.py` at your real Postgres tables instead
  of the mock lists

## Notes

- The maintenance/readiness data is **synthetic** - real naval maintenance
  records aren't public. This is standard practice for portfolio projects;
  just keep it labeled as simulated.
- Vessel position data should come from NOAA's public AIS feed for realism.
