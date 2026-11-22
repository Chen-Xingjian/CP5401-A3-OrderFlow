#!/bin/sh
# Launch the single-page shop using the local SQLite database.
set -eu
umask 077
cd "$(dirname "$0")/.."
if [ -z "${ORDERFLOW_DB_PATH:-}" ] && [ -f .local-review/data/PG_VERSION ] && [ ! -e .local-review/orderflow.sqlite3 ]; then
    echo "Existing PostgreSQL review data found. Follow the one-time import in README.md." >&2
    exit 1
fi
exec python -m streamlit run src/app.py --server.address 127.0.0.1 \
    --server.port "${ORDERFLOW_PORT:-8514}" --server.headless true
