# OrderFlow

A campus print-shop customer orders a single catalogue service and follows its progress through collection. Staff confirm an order, start work, mark it ready for pickup and record handover. This repository contains the order service and PostgreSQL baseline for development round R2.

**Review state** — The student accepted R1-01 on 17 November 2026. Candidate R2-01 awaits student acceptance. The two roles in the examples below are fictional fixtures. The interactive Python session is a local acceptance tool with direct access to the service. The authenticated Streamlit application belongs to R3.

## Run the checks

With Docker Compose, from the repository root, run:

```sh
docker compose run --build --rm checks
```

For a native run, use Python 3.12 and PostgreSQL 16. With `initdb`, `pg_ctl` and `createdb` on PATH:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
sh scripts/local-pg.sh sh scripts/check.sh
```

The native helper starts a private socket-only server, creates the disposable test database and stops the server on exit. An existing dedicated database named `orderflow_test` also works. Set `TEST_DATABASE_URL` and run `sh scripts/check.sh`. Each integration case has its own schema. The quality workflow calls the same check script on pull requests targeting main and pushes to main. Results appear in the run log and its JUnit artifact.

## Try the core by hand

Launch the review shell using one of the following commands. Both start with empty orders and fictional accounts.

```sh
docker compose run --build --rm -e PYTHONPATH=src checks python -m support.review
# With the native environment above:
sh scripts/local-pg.sh env PYTHONPATH=src python -m support.review
```

Enter one line at a time at the Python prompt:

```python
order = service.create_order(a, service_id="bw-print", quantity=2)
order.status, order.version, len(service.get_order(a, order.id).history)
service.list_orders(b)
service.get_order(b, order.id)
service.advance_order(staff, order.id, target="COMPLETED", expected_version=0)
service.get_order(a, order.id)
service.advance_order(staff, order.id, target="CONFIRMED", expected_version=0)
service.advance_order(staff, order.id, target="CONFIRMED", expected_version=0)
[(e.sequence, e.to_status, e.actor_id) for e in service.get_order(a, order.id).history]
```

Expect `('PENDING', 0, 1)`, then an empty customer B list. B's detail lookup reports “No accessible order was found.” The premature handover is refused. Re-reading the detail shows the original order with one event. Staff confirmation succeeds once. Replaying version zero reports “This order changed. Refresh before continuing.” The last expression yields two events, from customer A and staff S. Exceptions leave the shell open. Press Ctrl-D to exit and discard this shop.

## Database and source

| Path | Purpose |
|---|---|
| `src/orderflow/services.py` | Four service calls, live role checks, per-call transactions and version comparison |
| `src/orderflow/rules.py` | Input boundaries and four legal forward transitions |
| `src/orderflow/repository.py` | Scoped queries, row lock, order write and history append |
| `db/migrations/001_baseline.sql` | User identities, catalogue, orders, history and three fictional catalogue rows |
| `src/orderflow/db.py` | Connection setup, UTC transaction scope and checksummed migration |
| `tests/integration/test_transactions.py` | History and commit faults, two-connection contention |
| `docs/evidence/R2-01/` | Local run, machine-readable results, negative control and candidate file hashes |

To initialise a separate development database, supply its PostgreSQL URL as `DATABASE_URL` and run `PYTHONPATH=src python -m orderflow.db` from the repository root. The migration runs in a transaction and checks its previous checksum before reapplying. It seeds the catalogue. Test identities are created only in the isolated acceptance schemas. Server-side login and credentials are part of the R3 design.

See the [requirements](docs/requirements.md), [test map](docs/test-plan.md), [R1 decision](docs/iterations/R1-01-decision.md) and [R2 acceptance report](docs/iterations/R2-01.md).
