#!/bin/sh
# Run a command from the project root against its own socket-only PostgreSQL cluster.
set -eu
if [ "$#" -eq 0 ]; then
    echo "Usage: sh scripts/local-pg.sh COMMAND [ARGUMENT ...]" >&2
    exit 2
fi
for binary in initdb pg_ctl createdb; do
    command -v "$binary" >/dev/null || { echo "Missing PostgreSQL tool: $binary" >&2; exit 2; }
done
scratch=$(mktemp -d /tmp/orderflow.XXXXXXXX)
cleanup() {
    if [ -f "$scratch/data/postmaster.pid" ]; then
        pg_ctl -D "$scratch/data" -m fast -w stop >/dev/null || return
    fi
    rm -rf "$scratch"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
initdb -D "$scratch/data" -U orderflow_test --auth-local=trust --auth-host=reject \
    --no-locale --encoding=UTF8 > "$scratch/init.log"
pg_ctl -D "$scratch/data" -l "$scratch/server.log" -w \
    -o "-c listen_addresses='' -c unix_socket_directories='$scratch' -c timezone=UTC" start >/dev/null
createdb -h "$scratch" -U orderflow_test orderflow_test
export TEST_DATABASE_URL="postgresql+psycopg://orderflow_test@/orderflow_test?host=$scratch"
"$@"
