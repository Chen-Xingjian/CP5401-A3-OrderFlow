# OrderFlow

OrderFlow tracks campus print orders from submission to collection. Customers follow their own orders. Staff share a queue and record who confirmed an order, started printing, marked it ready and handed it over. An order reaches **Completed** when the customer receives the prints.

[Open the public Streamlit demo](https://cp5401-orderflow.streamlit.app/)

## Try the shop

| Demo user | What to try |
| --- | --- |
| **Customer** · Alex or Blair | Place an order, refresh its status and read its history. The owner can cancel while the order is **Pending confirmation** or **Confirmed**. Starting production closes that window. |
| **Staff** · Sam or Taylor | Select an order in **Shop queue** and advance it. Filter by status or **Pickup overdue**. Select **Confirm handover** after giving the prints to the customer. |

For a repeatable example, select **Start demo scenario**. The private queue opens as Sam with two ready orders. Blair’s *Workshop handouts* have waited 50 hours, while Alex’s *Library posters* have just become ready. Select **Pickup overdue (1)** and confirm handover for Blair’s order. The overdue count drops to zero. **Clear filter** shows the full queue. **Restart demo scenario** creates a fresh pair in this visitor’s session, and **Return to shop** reopens the shared workspace.

The demo lets visitors switch among four fictional identities. Use fictional order details. The shared shop stores data in a SQLite file local to its Streamlit instance, which may be reset when the instance restarts.

## Releases and assessment evidence

| Release | What changed | Where to check it |
| --- | --- | --- |
| [V1.0 baseline](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/releases/tag/v1.0.0) | Customer order visibility, staff handover and five attributed history events | [Hosted acceptance and release decision](docs/iterations/V1.0-acceptance.md) |
| [V1.1 assessed change](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/releases/tag/v1.1.0) | CR001 added owner cancellation before production | [Issue #2 and impact analysis](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/issues/2), [merged PR #3](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/pull/3), [seven hosted checks on four orders](docs/iterations/V1.1-acceptance.md) |
| [V1.2](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/releases/tag/v1.2.0) | Staff workload filters and the private pickup scenario | The release records the overdue filter, handover, reset and two-visitor isolation checks. |
| [V1.2.1](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/releases/tag/v1.2.1) | Customer pickup reminders after 48 hours and readable names in order history | The release records the time-boundary checks and hosted customer observations. |

For the CR001 review, start with the [AI-assisted change intake](docs/iterations/R6-01.md). The [review findings and retest](docs/iterations/R7-01.md) explain why the first candidate required changes and how the warm upgrade and V1.0 migration checks were verified. The [merged-commit CI run](https://github.com/Chen-Xingjian/CP5401-A3-OrderFlow/actions/runs/45014647604) records 121 passing tests before hosted acceptance.

## Run locally

Use Python 3.12 and SQLite 3.35 or newer. From the repository root, run:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
sh scripts/review-app.sh
```

Open [the local shop](http://127.0.0.1:8514). The first launch creates the catalogue and fictional users. Relaunching the app reopens `.local-review/orderflow.sqlite3`. Set `ORDERFLOW_DB_PATH` to use another file. For an existing R3 PostgreSQL shop, see the [one-time import instructions](docs/database-choice.md#import-an-existing-r3-shop).

## Run the quality checks

With the virtual environment active, run:

```sh
python -m pip install -r requirements-dev.txt
sh scripts/check.sh
```

The [GitHub Actions workflow](.github/workflows/quality-checks.yml) runs the same script on pull requests targeting `main` and on pushes to `main`. It checks dependencies, runs Ruff lint and format checks, executes pytest with temporary SQLite databases and uploads reports including JUnit XML.

## Repository guide

| Location | Contents |
| --- | --- |
| [src](src/) and [db/migrations](db/migrations/) | Streamlit entry point, order rules, services, persistence and ordered SQL migrations |
| [tests](tests/) and [support](support/) | Unit and integration tests, database fixtures, review tools and the historical shop importer |
| [Requirements](docs/requirements.md) and [test plan](docs/test-plan.md) | Business and quality requirements, acceptance scenarios and their corresponding tests |
| [Iteration records](docs/iterations/), [evidence](docs/evidence/) and [AI-use log](docs/ai-use.csv) | Decisions made in each round, original test results, source snapshots and recorded AI assistance |
