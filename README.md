# OrderFlow

OrderFlow tracks campus print orders through pickup. Customers order one print service and follow its progress. Staff see the shop queue, record production and confirm physical handover. R3-01 was accepted by the student. R4 presents the entire review shop on one page.

## Use the demo

Select **Customer** and choose **Alex** or **Blair** in **Demo user**. Place an order or review that customer's orders on the same page. Select **Staff** to open the shared shop queue as **Sam** or **Taylor**. The selected staff member is recorded on each update. Mark the prints ready when production finishes. Select **Confirm handover** only after handing them to the customer.

Anyone with app access can select any of the four fictional identities. The selector demonstrates role and ownership rules. Use a dedicated database containing only fictional orders and notes.

## Run the local review application

Use Python 3.12 and PostgreSQL 16 with initdb, pg_ctl, psql and createdb on PATH. From the project root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
sh scripts/review-app.sh
```

Open http://127.0.0.1:8513. The launcher stores the local shop under the ignored directory `.local-review/`. Restarting it reopens the same shop. Stop the app with Ctrl-C. To stop its database, run `pg_ctl -D .local-review/data -m fast -w stop`.

## Deploy on Streamlit Community Cloud

Connect the GitHub repository, choose branch `main`, set the entry point to `src/app.py` and select Python 3.12 in Advanced settings. Configure the root-level secret `DATABASE_URL` with the TLS connection string for a dedicated hosted PostgreSQL database. Use the database provider's session-compatible connection and a user with permission to create the schema objects. Keep the real connection string in the platform's secrets. Startup applies versioned migrations and adds missing fictional identities. Existing demo orders and history remain in PostgreSQL across application restarts.

For release verification, record the deployed commit, actual app URL and CI run. Open a fresh browser session and confirm the shop renders both selectors and the catalogue. Place an identifiable fictional order, switch users and verify customer isolation and staff attribution. Reboot the cloud app and reopen the same order to verify persistence. Record the observations before requesting student acceptance.

## Run the checks

```sh
python -m pip install -r requirements-dev.txt
sh scripts/local-pg.sh sh scripts/check.sh
```

Alternatively run `docker compose run --build --rm checks`. CI invokes the same check script against its own PostgreSQL service. Tests create isolated schemas. The UI suite exercises role and user switching, account deactivation, stale staff actions and the handover flow using the real service and database.

## Project records

- [Approved requirements](docs/requirements.md)
- [R2 acceptance decision](docs/iterations/R2-01-decision.md)
- [R3 implementation and student review](docs/iterations/R3-01.md)
- [Test map](docs/test-plan.md)

- [R3 acceptance decision](docs/iterations/R3-01-decision.md)
- [R4 release verification](docs/iterations/R4-01.md)
