# OrderFlow

OrderFlow tracks campus print orders through pickup. Customers order one print service and follow its progress. Staff see the shop queue, record production and confirm physical handover. R2-01 was accepted on 22 November 2026. The English Streamlit interface in R3-01 awaits student review.

## Run the local review application

Use Python 3.12 and PostgreSQL 16 with initdb, pg_ctl, psql and createdb on PATH. From the project root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
sh scripts/review-app.sh
```

Open http://127.0.0.1:8513. The launcher creates a private, local PostgreSQL cluster, applies the migrations and provisions alex and blair (customers) and sam (staff) on first use. Find their generated passwords in `.local-review/accounts.txt`. This private file and the database are excluded from version control and distribution. The database stores salted scrypt verifiers. Sign out before switching accounts in the same browser. Reuse the launcher to reopen the same local shop.

Stop the app with Ctrl-C. To stop its local database, run `pg_ctl -D .local-review/data -m fast -w stop`. For a separate configured environment, supply DATABASE_URL, run `PYTHONPATH=src python -m orderflow.db` and launch `python -m streamlit run src/app.py`. Fictional review accounts are provisioned only by the explicit local review setup.

## Review an order

Sign in as a customer and select **Place an order**. Staff open the matching ID in **Shop queue**, then confirm, start production and mark it ready for pickup. Customers use **Refresh orders** to see updates. Once the customer has received the prints, staff select **Confirm handover**. The history records who performed each step and when, in Singapore time.

## Run the checks

```sh
python -m pip install -r requirements-dev.txt
sh scripts/local-pg.sh sh scripts/check.sh
```

Alternatively run `docker compose run --build --rm checks`. CI invokes the same check script against its own PostgreSQL service. Tests create isolated schemas. The UI suite exercises sign-in, account switching, account deactivation, stale staff actions and the handover flow using the real service and database.

## Project records

- [Approved requirements](docs/requirements.md)
- [R2 acceptance decision](docs/iterations/R2-01-decision.md)
- [R3 implementation and student review](docs/iterations/R3-01.md)
- [Test map](docs/test-plan.md)
