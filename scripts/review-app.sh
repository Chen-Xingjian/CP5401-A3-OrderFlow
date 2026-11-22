#!/bin/sh
# Run the local review shop. Its PostgreSQL data survives a restart.
set -eu
umask 077
cd "$(dirname "$0")/.."
state="$PWD/.local-review"
mkdir -p "$state"
for binary in initdb pg_ctl createdb psql; do
    command -v "$binary" >/dev/null || { echo "Add PostgreSQL 16 tools to PATH." >&2; exit 2; }
done
if [ ! -f "$state/data/PG_VERSION" ]; then
    initdb -D "$state/data" -U orderflow --auth-local=trust --auth-host=reject \
        --no-locale --encoding=UTF8 > "$state/init.log"
fi
if ! pg_ctl -D "$state/data" status >/dev/null 2>&1; then
    pg_ctl -D "$state/data" -l "$state/postgres.log" -w \
        -o "-c listen_addresses='' -c unix_socket_directories='$state' -c timezone=UTC" start >/dev/null
fi
if [ "$(psql -h "$state" -U orderflow -d postgres -Atc "SELECT count(*) FROM pg_database WHERE datname='orderflow_review'")" = 0 ]; then
    createdb -h "$state" -U orderflow orderflow_review
fi
export DATABASE_URL="postgresql+psycopg://orderflow@/orderflow_review?host=$state"
export PYTHONPATH=src
exec python -m streamlit run src/app.py --server.address 127.0.0.1 \
    --server.port "${ORDERFLOW_PORT:-8513}" --server.headless true
