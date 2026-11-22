# OrderFlow

OrderFlow tracks campus print orders through pickup. Customers order one print service and follow its progress. Staff see the shop queue, record production and confirm physical handover. R3-01 was accepted by the student. R4 presents the entire review shop on one page.

## Use the demo

Select **Customer** and choose **Alex** or **Blair** in **Demo user**. Place an order or review that customer's orders on the same page. Select **Staff** to open the shared shop queue as **Sam** or **Taylor**. The selected staff member is recorded on each update. Mark the prints ready when production finishes. Select **Confirm handover** only after handing them to the customer.

Anyone with app access can select any of the four fictional identities. The selector demonstrates role and ownership rules. Use a dedicated database containing only fictional orders and notes.

On the V1.1 candidate, customers can choose **Cancel order** on their own orders until staff start production. A cancelled order stays in **My orders** and the **Shop queue** with its history. The staff workflow ends for that order. A stale page prompts the user to refresh.

## Run the local review application

Use Python 3.12 with its bundled SQLite library (SQLite 3.35 or newer). From the project root:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
sh scripts/review-app.sh
```

Open http://127.0.0.1:8514. The application creates the catalogue and demo identities on first use. Orders and their histories are stored in `.local-review/orderflow.sqlite3`. Stop the app with Ctrl-C and relaunch it to reopen the same file. Set `ORDERFLOW_DB_PATH` to use a different SQLite file. The local review requires no database server, secrets or hosting account.

### Carry over an earlier local PostgreSQL shop

If you already have an R3 shop in this project directory, keep the old database running for the one-time import. With its original local `psql` available on PATH, run `PYTHONPATH=src python -m support.import_review` before the first SQLite launch. The importer copies and compares identities, catalogue, orders and events from one read-only snapshot. It publishes a new file only after all four tables match and refuses to overwrite an existing SQLite file. Legacy password records stay with the old database. An empty installation can launch directly.

## Run the checks

```sh
python -m pip install -r requirements-dev.txt
sh scripts/check.sh
```

CI runs the same command on isolated, temporary SQLite files. Tests cover the order lifecycle, customer boundaries, stale staff updates, writer contention, rollback at commit, migration and single-page role switching.

## V1.0 baseline

The student accepted the local SQLite candidate v1.0.0-rc.2 on 22 November 2026 after checking customer order visibility and staff handover attribution. The SQLite demo is [live on Streamlit Community Cloud](https://cp5401-orderflow.streamlit.app/). On 22 November 2026 an independent visitor session opened the customer order form without signing in.

The student accepted the hosted workflow on order `12E39BC5` and authorised the formal release. [Hosted acceptance record](docs/iterations/V1.0-acceptance.md) · [V1.0 release](https://github.com/Chen-Xingjian/CP5401-OrderFlow/releases/tag/v1.0.0)

## Project records

- [Approved requirements](docs/requirements.md)
- [R2 acceptance decision](docs/iterations/R2-01-decision.md)
- [R3 implementation and student review](docs/iterations/R3-01.md)
- [Test map](docs/test-plan.md)
- [R3 acceptance decision](docs/iterations/R3-01-decision.md)
- [R4 release verification](docs/iterations/R4-01.md)

- [R4-02 local acceptance decision](docs/iterations/R4-02.md)
