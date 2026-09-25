-- Naval Fleet Readiness & Maintenance Intelligence Platform
-- Star schema: fact + dimension tables (PostgreSQL)

-- ===== Dimension tables =====

CREATE TABLE IF NOT EXISTS dim_base (
    base_id     SERIAL PRIMARY KEY,
    base_name   TEXT NOT NULL,
    region      TEXT
);

CREATE TABLE IF NOT EXISTS dim_vessel (
    vessel_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    vessel_type  TEXT NOT NULL,
    base_id      INTEGER REFERENCES dim_base(base_id)
);

CREATE TABLE IF NOT EXISTS dim_equipment (
    equipment_id    SERIAL PRIMARY KEY,
    equipment_type  TEXT NOT NULL,
    install_date    DATE
);

CREATE TABLE IF NOT EXISTS dim_date (
    date     DATE PRIMARY KEY,
    day      INTEGER,
    month    INTEGER,
    quarter  INTEGER,
    year     INTEGER
);

-- ===== Fact tables =====

CREATE TABLE IF NOT EXISTS fact_vessel_positions (
    id          BIGSERIAL PRIMARY KEY,
    vessel_id   TEXT REFERENCES dim_vessel(vessel_id),
    "timestamp" TIMESTAMPTZ NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    speed_knots DOUBLE PRECISION,
    heading_deg DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS fact_maintenance_events (
    id             BIGSERIAL PRIMARY KEY,
    vessel_id      TEXT REFERENCES dim_vessel(vessel_id),
    equipment_id   INTEGER REFERENCES dim_equipment(equipment_id),
    event_date     DATE NOT NULL,
    downtime_hrs   DOUBLE PRECISION,
    event_type     TEXT  -- 'scheduled' | 'unscheduled' | 'inspection'
);

CREATE TABLE IF NOT EXISTS fact_readiness_status (
    id               BIGSERIAL PRIMARY KEY,
    vessel_id        TEXT REFERENCES dim_vessel(vessel_id),
    date             DATE NOT NULL,
    readiness_score  DOUBLE PRECISION,  -- 0-100
    status           TEXT  -- 'ready' | 'limited' | 'unavailable'
);

-- Helpful indexes for the query patterns the LLM layer will generate
CREATE INDEX IF NOT EXISTS idx_positions_vessel_ts ON fact_vessel_positions (vessel_id, "timestamp");
CREATE INDEX IF NOT EXISTS idx_maintenance_vessel_date ON fact_maintenance_events (vessel_id, event_date);
CREATE INDEX IF NOT EXISTS idx_readiness_vessel_date ON fact_readiness_status (vessel_id, date);
