#!/usr/bin/env bash
# IAmDataEng — star-schema-ecommerce devcontainer bootstrap.
#
# Runs once when the Codespace is created:
#   1. Install Python deps (dbt-core, dbt-postgres, sqlfluff, pytest, ...)
#   2. Start a Postgres 16 container (host: localhost:5432)
#   3. Seed the OLTP-dump CSVs into the bronze schema (~500k order lines)
#   4. Materialize the dbt profile from the .example template
#
# The learner can re-run this script at any time:
#     bash .devcontainer/post-create.sh
#
# Idempotent: re-runs do not recreate the Postgres container if it already exists,
# they only restart it; fixture generation is skipped if the CSV files already exist.

set -euo pipefail

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WORKSPACE_DIR"

echo ">> [1/4] Installing Python dependencies (dbt-core 1.7, dbt-postgres 1.7, sqlfluff 3.x, pytest)..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ">> [2/4] Starting Postgres 16 via docker compose..."
docker compose -f .devcontainer/docker-compose.yml up -d
# Wait for Postgres to accept connections (max 60s).
for i in $(seq 1 60); do
  if docker compose -f .devcontainer/docker-compose.yml exec -T postgres pg_isready -U rundle -d rundle_warehouse >/dev/null 2>&1; then
    echo "   postgres is ready"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "ERROR: postgres did not become ready in 60s. Check 'docker compose logs postgres'."
    exit 1
  fi
  sleep 1
done

echo ">> [3/4] Generating fixture CSVs (deterministic, seed=42) and loading bronze..."
if [ ! -f fixtures/oltp_dump/order_lines.csv ]; then
  python -m fixtures.generate_fixtures
else
  echo "   fixtures already present, skipping generation"
fi
python -m fixtures.load_bronze

echo ">> [4/4] Materializing dbt profile and verifying connectivity..."
mkdir -p "$HOME/.dbt"
if [ ! -f .dbt/profiles.yml ]; then
  mkdir -p .dbt
  cp profiles.yml.example .dbt/profiles.yml
fi
dbt --version
dbt debug --profiles-dir .dbt || {
  echo "ERROR: dbt debug failed. Check .dbt/profiles.yml and the postgres container logs."
  exit 1
}

echo ""
echo "================================================================"
echo "Setup complete. Next steps:"
echo "  1. Read README.fr.md."
echo "  2. Build the staging models, then dim_*.sql and fct_*.sql."
echo "  3. Run:  dbt build --profiles-dir .dbt"
echo "  4. Run:  pytest tests/ -v"
echo "================================================================"
