"""Bronze loader — pipes the seven OLTP-dump CSVs into Postgres bronze schema.

Idempotent: drops and recreates the bronze schema each run. This is intentional:
the OLTP dump is the SOURCE OF TRUTH for the learner's models — re-running the
loader resets the playground without touching staging / marts.

Connection comes from env vars (set by the devcontainer or a local .env). The
Postgres COPY command is used for bulk insert (50-100x faster than executemany).

Schemas created:

    bronze              -- mirror of the OLTP dump, 7 tables
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2

FIXTURES_DIR = Path(__file__).resolve().parent / "oltp_dump"

BRONZE_SCHEMA_SQL = """
DROP SCHEMA IF EXISTS bronze CASCADE;
CREATE SCHEMA bronze;

CREATE TABLE bronze.countries (
    country_code  TEXT PRIMARY KEY,
    country_name  TEXT NOT NULL,
    region        TEXT NOT NULL
);

CREATE TABLE bronze.channels (
    channel_id    TEXT PRIMARY KEY,
    channel_name  TEXT NOT NULL,
    channel_type  TEXT NOT NULL
);

CREATE TABLE bronze.dates (
    date_key      INTEGER PRIMARY KEY,
    date_iso      DATE NOT NULL,
    day           INTEGER NOT NULL,
    month         INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    year          INTEGER NOT NULL,
    day_of_week   INTEGER NOT NULL,
    is_weekend    INTEGER NOT NULL
);

CREATE TABLE bronze.products (
    product_id        BIGINT PRIMARY KEY,
    product_name      TEXT NOT NULL,
    category_code     TEXT NOT NULL,
    list_price_eur    NUMERIC(10, 2) NOT NULL
);

CREATE TABLE bronze.customers (
    customer_id   BIGINT PRIMARY KEY,
    email         TEXT NOT NULL,
    country_code  TEXT NOT NULL,
    signup_date   DATE NOT NULL,
    segment       TEXT NOT NULL
);

CREATE TABLE bronze.orders (
    order_id      BIGINT PRIMARY KEY,
    -- customer_id intentionally NOT a FK at bronze. The learner discovers the
    -- late-arriving customers issue when joining staging → dim.
    customer_id   BIGINT NOT NULL,
    channel_id    TEXT NOT NULL,
    country_code  TEXT NOT NULL,
    order_date    DATE NOT NULL,
    ship_date     DATE NOT NULL,
    status        TEXT NOT NULL
);

CREATE TABLE bronze.order_lines (
    order_id          BIGINT NOT NULL,
    line_number       INTEGER NOT NULL,
    product_id        BIGINT NOT NULL,
    quantity          INTEGER NOT NULL,
    unit_price_eur    NUMERIC(10, 2) NOT NULL,
    discount_eur      NUMERIC(10, 2) NOT NULL,
    PRIMARY KEY (order_id, line_number)
);
"""

# (csv_filename, schema.table) — order matters: parents before children for any FK
# you might add later (none on bronze, but the convention helps).
LOAD_PLAN = [
    ("countries.csv", "bronze.countries"),
    ("channels.csv", "bronze.channels"),
    ("dates.csv", "bronze.dates"),
    ("products.csv", "bronze.products"),
    ("customers.csv", "bronze.customers"),
    ("orders.csv", "bronze.orders"),
    ("order_lines.csv", "bronze.order_lines"),
]


def _connect() -> psycopg2.extensions.connection:
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "rundle"),
        password=os.environ.get("PGPASSWORD", "rundle_dev_password"),
        dbname=os.environ.get("PGDATABASE", "rundle_warehouse"),
    )


def load() -> None:
    missing = [
        name for name, _ in LOAD_PLAN if not (FIXTURES_DIR / name).exists()
    ]
    if missing:
        print(
            f"ERROR: missing fixture files: {missing}\n"
            f"Run `python -m fixtures.generate_fixtures` first.",
            file=sys.stderr,
        )
        sys.exit(1)

    with _connect() as conn:
        with conn.cursor() as cur:
            print(">> dropping and recreating schema bronze")
            cur.execute(BRONZE_SCHEMA_SQL)
            for filename, table in LOAD_PLAN:
                path = FIXTURES_DIR / filename
                print(f">> COPY {path.name} -> {table}")
                with path.open("r", encoding="utf-8") as f:
                    cur.copy_expert(
                        f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true)",
                        f,
                    )
            # Counts for the operator log.
            for _, table in LOAD_PLAN:
                cur.execute(f"SELECT count(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"   {table}: {count} rows")
        conn.commit()
    print(">> bronze load complete")


if __name__ == "__main__":
    load()
