# Database assessment for R2-01

Assessment date is 17 November 2026. The recommendation assumes a Streamlit Community Cloud deployment with orders retained across application sessions and deployment lifecycle events. The hosting service and database provider remain to be selected and verified.

## Assignment and approved behaviour

A3 describes a small application as the vehicle for software quality engineering on page 2. Its minimum requirements on page 3 include correctly managed information, important business rules, automated tests, CI and a browser-accessible application. The HD rubric on pages 10–12 assesses realistic testable requirements, reliable behaviour, traceability and credible quality evidence. It leaves the database product open. PostgreSQL was an architectural choice in the project plan. SQLite could support the same assessed business behaviour.

R1-01 requires atomic order and history writes, customer-scoped access, a useful response to stale staff requests and data retained when a connection is reopened. Both engines can implement those contracts. The transaction and concurrency experiments must exercise the engine selected for deployment.

## Candidate comparison

| Consideration | Local SQLite file | External PostgreSQL |
|---|---|---|
| Setup | Embedded database, Python includes its driver, one local database file | A running database service, driver and connection configuration |
| This order volume | Suitable for a small shop with short, infrequent writes | Also suitable for the same workload |
| Concurrent staff | Serialise writes and recheck the observed version with appropriate waiting and bounded retry | Lock the target order row, wait for a competing commit, then check its version |
| Rollback and history | Use a database transaction covering both writes | Use a database transaction covering both writes |
| Local persistence | Retained while the database file and its storage are retained | Retained by the configured database storage |
| Community Cloud persistence | Local filesystem retention requires a separate solution | App connects to independently hosted storage |
| R2 implementation effort | Adapt SQL, transaction handling, fixtures and integration tests | Existing 88 passing cases exercise this engine |

SQLite is designed for low-administration application storage and is suitable for many small web applications. Its Python driver is supplied with Python. This makes it the lighter runtime choice for a local prototype or a single application host with reliable persistent storage. [SQLite usage guidance](https://www.sqlite.org/whentouse.html), [Streamlit data connections](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data)

SQLite permits one write transaction at a time. WAL permits readers and a writer to run concurrently. For this shop, a short transaction using BEGIN IMMEDIATE, version checks and bounded waiting could satisfy the two-staff rule. A busy database requires a retry or storage response appropriate to the actual failure. The application should report STALE_VERSION when it has established that the version changed. [SQLite transactions](https://www.sqlite.org/lang_transaction.html), [SQLite WAL concurrency](https://www.sqlite.org/wal.html)

PostgreSQL SELECT FOR UPDATE waits for a competing writer on the same row. Under the current READ COMMITTED setup, the subsequent version comparison uses the committed row it obtains. This is the mechanism exercised by T17. [PostgreSQL 16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html)

Streamlit supports SQLite, but its Community Cloud documentation explicitly leaves local file persistence unguaranteed. An order database stored in that filesystem needs a separate durable-storage design. A hosted PostgreSQL connection addresses the storage location directly. Provider retention, configuration and application reconnect behaviour still need deployment verification. [Streamlit data connections](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data)

## Recommendation for this candidate

Keep the single PostgreSQL database for the current Community Cloud direction. Use a single schema migration and the existing short service calls. The reason is the fit between deployment storage and the approved consistency contracts. The project can demonstrate HD quality work with either engine through suitable requirements, tests, human review and controlled change evidence.

Choose SQLite if the intended deployment becomes a single host with reliable retained disk and the priority is eliminating a separate database service. That choice would be a revision within R2. Carry over the approved input, access and lifecycle behaviour, then verify rollback, two independent connections, stale-version response and persistent file reopening on the revised candidate.

## Scope of a SQLite revision

| File or area | Work required |
|---|---|
| src/orderflow/db.py | SQLite driver configuration, transaction control, foreign keys, lock waiting and migration coordination |
| db/migrations/001_baseline.sql | Replace PostgreSQL enum and time functions, specify UUID and UTC timestamp representations, preserve checks and references |
| src/orderflow/repository.py | Replace FOR SHARE and FOR UPDATE with the chosen SQLite transaction and conditional update approach |
| support/sandbox.py | One temporary database file per case in place of PostgreSQL schemas |
| tests/integration/test_transactions.py | Adapt PL/pgSQL faults, deferred commit fault and the lock rendezvous to SQLite while retaining the failure contracts |
| scripts, Compose and CI | Use the same engine as deployment and supply a file retention and recovery procedure |

This assessment records a recommendation. R2-01 remains the PostgreSQL implementation whose source manifest is already attached to its report. The SQLite alternative has been assessed from documentation and code, and has yet to be implemented or benchmarked in this project.
