-- Operational schema for the network operations platform (PostgreSQL).
-- Recreated from scratch by `python init_db.py`.

DROP SCHEMA IF EXISTS bi CASCADE;
DROP TABLE IF EXISTS interventions, tickets, kpi_stats, antenna_config,
                     site_code_pools, site, users CASCADE;

CREATE TABLE users (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name             TEXT NOT NULL,
    user_id          TEXT NOT NULL UNIQUE,
    email            TEXT UNIQUE,
    profile          TEXT NOT NULL CHECK (profile IN ('engineer', 'technician', 'administrator', 'manager')),
    password         TEXT NOT NULL,
    is_active        BOOLEAN NOT NULL DEFAULT TRUE,
    activation_token TEXT,
    token_expiry     TIMESTAMP,
    twofa_code       TEXT,
    twofa_expiry     TIMESTAMP,
    last_2fa_sent    TIMESTAMP,
    created_at       TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE site (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region      TEXT NOT NULL,
    code        TEXT NOT NULL,
    delegation  TEXT NOT NULL,
    site_name   TEXT NOT NULL,
    x           TEXT NOT NULL,   -- latitude
    y           TEXT NOT NULL,   -- longitude
    hba         TEXT NOT NULL,   -- antenna height (m)
    supplier    TEXT NOT NULL,
    access      TEXT NOT NULL,
    antenna     TEXT NOT NULL,
    surface     TEXT NOT NULL,
    UNIQUE (region, code, delegation)
);

CREATE TABLE antenna_config (
    id               INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id          INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    secteur          TEXT,
    azimut           INTEGER,
    pire             REAL,
    tilt_mecanique   REAL,
    tilt_electrique  REAL
);
CREATE INDEX idx_antenna_site ON antenna_config(site_id);

-- One row per site per day; logging the same day again updates it.
CREATE TABLE kpi_stats (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id             INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    date                DATE NOT NULL,
    taux_blocage        DOUBLE PRECISION,   -- call blocking rate (%)
    taux_coupure        DOUBLE PRECISION,   -- call drop rate (%)
    taux_disponibilite  DOUBLE PRECISION,   -- availability (%)
    trafic_voix_erlang  DOUBLE PRECISION,
    trafic_data_go      DOUBLE PRECISION,
    trafic_volte_go     DOUBLE PRECISION,
    logged_at           TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (site_id, date)
);
CREATE INDEX idx_kpi_date ON kpi_stats(date);

CREATE TABLE site_code_pools (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region      TEXT NOT NULL,
    start_code  INTEGER NOT NULL,
    end_code    INTEGER NOT NULL
);

CREATE TABLE tickets (
    id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    site_id        INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    engineer_id    INTEGER NOT NULL REFERENCES users(id),
    technician_id  INTEGER NOT NULL REFERENCES users(id),
    title          TEXT NOT NULL,
    description    TEXT,
    priority       TEXT NOT NULL DEFAULT 'Medium',
    status         TEXT NOT NULL DEFAULT 'Open',
    created_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE interventions (
    id                INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticket_id         INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    technician_id     INTEGER NOT NULL REFERENCES users(id),
    date              TIMESTAMP NOT NULL DEFAULT now(),
    details           TEXT NOT NULL,
    engineer_rating   INTEGER CHECK (engineer_rating BETWEEN 1 AND 5),
    engineer_comment  TEXT
);
