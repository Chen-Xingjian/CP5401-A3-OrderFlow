# R1 acceptance scenarios and R2 evidence

The test oracles below follow the accepted business rules. Test function names carry the T identifiers. Parameterized inputs count as separate executed cases. The local result is in [local-check.log](evidence/R2-01/local-check.log).

| R1 scenario | R2 tests | Expected observation |
|---|---|---|
| AC-01, valid creation | T01, T09, T19 | A owns a quantity-two pending order and sequence-zero creation event. Opening a new connection preserves both. |
| AC-02, input boundaries | T02, T03 | 1 and 99, empty and 500-character notes succeed. Rejected requests leave both tables unchanged. The persisted service name comes from the catalogue. |
| AC-03, visibility | T04–T08, T12 | Two customers have independent lists. Unknown and inaccessible details share the same error. Staff can read both customers' histories. R3 T20 also covers the interface. |
| AC-04, normal lifecycle | T09, T10 | Four staff actions produce version four and five ordered events. READY_FOR_PICKUP precedes physical handover. |
| AC-05, denied operations | T11–T13, T18 | Rejected transitions preserve the full snapshot. Two orders retain isolated versions and event actors. |
| AC-06, transaction failure | T15, T16 | A real PostgreSQL trigger interrupts before history insertion or at deferred commit. A separate connection sees the original order and events. |
| AC-07, concurrent staff | T14, T17 | The update based on an old version returns STALE_VERSION, including when two connections reach the row lock together. |
| AC-08, reproducibility and user judgement | Local check script and GitHub workflow | Local execution is recorded. PR execution, deployed UI observation and VAL-01 remain pending. |

The three key run records are [JUnit results](evidence/R2-01/junit.xml), [fault and race output](evidence/R2-01/local-check.log) and [test sensitivity](evidence/R2-01/negative-control.log). R3 T20 runs against the Streamlit interface and an isolated PostgreSQL schema. VAL-01 remains a separate human observation. T21–T28 apply to the separately approved change after V1.0 release.

## Human review

Use the handover scenario in the [R3 review](iterations/R3-01.md). Record the candidate ID, what you tried, what you observed, any concern and the reason for your decision. A later repository commit or PR run should identify the exact revision it checked.

## R3 interface checks

T20 covers customer order submission, staff access and customer isolation on account switching, live status refresh, ready versus handed over, generic sign-in errors, account deactivation and a stale action from a second staff session. The local review record links to the actual results. The R2 T19 migration assertion now checks both migration names after reconnecting and reapplying migrations.

## R4 demo and deployment

T20 now exercises one-page role and user switching, customer drafts and order isolation, inactive accounts, stale staff updates and individual handover attribution. A separate test reruns demo provisioning against existing orders. Hosted release verification checks the actual deployed revision, UI and order history after application restart. The student evaluates the business outcome after hosted checks.

## R4-02 SQLite verification

The current suite runs on temporary SQLite files. T15–T16 use a history trigger for a statement failure and a deferred foreign-key violation for a commit failure. T17 synchronises two staff connections after reading the same version. T19 reopens the file and reapplies migrations. Import checks preserve order history, reject overwrite and discard failed copies.


## R6 cancellation regression

| Cases | Oracle and evidence |
| --- | --- |
| T21–T22 | An eligible owner adds one attributed event. At or after production, the entire order and history match their pre-request snapshot. Unit and SQLite tests check both sides of the cutoff. |
| T23–T24 | The service checks access before version or state. Cross-customer and missing-order results match. Old and current-version retries have distinct outcomes. Every attempted staff transition from Cancelled fails. |
| T25 | Two connections read the same confirmed version before competing. Only one commits, and its actor and target match the last history event. |
| T26 | A history-write trigger or a deferred constraint interrupts cancellation. A separate read sees the original confirmed order and both previous events. |
| T27 | Verify migrations 001 and 002 against their released V1.0 checksums. Upgrade a backup of a populated V1.0 file twice. Compare full snapshots for two owners, check foreign keys and the owner index, then progress a legacy order. With a warm Streamlit cache, cancel an existing order on the first attempt after upgrade and verify its history. |
| T28 | Streamlit AppTest checks eligible and ineligible views, owner switching, cancelled history in the staff queue, and stale-page refresh feedback. |

The original T19 migration inventory now includes the third checksum-tracked migration. The V1.0 test cases still run in the complete suite. The student's manual VAL-02 review is tracked separately in the R6 report.

### CR002 workload and pickup time

T29 checks the instant before, at and after 48 hours using a fixed observation time, including different UTC offsets. T30 checks staff-only access, consistent cross-customer metrics, stable repeated reads, removal on handover, and the customer view. For human validation, ask a staff reviewer to find an overdue order, refresh, then hand it over and explain the change in both counts and order history.
