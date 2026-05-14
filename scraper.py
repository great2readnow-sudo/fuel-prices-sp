CREATE TABLE stations (
  id          TEXT PRIMARY KEY,
  name        TEXT,
  region      TEXT,
  commune     TEXT,
  brand       TEXT
);

CREATE TABLE prices (
  id          BIGSERIAL PRIMARY KEY,
  station_id  TEXT,
  fuel_type   TEXT,
  price       INT,
  scraped_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE averages (
  fuel_type   TEXT PRIMARY KEY,
  price       INT,
  updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE regions (
  region          TEXT PRIMARY KEY,
  min_price       INT,
  avg_price       INT,
  station_count   INT,
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);
