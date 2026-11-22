# R1 acceptance scenarios and R2 evidence

The test oracles below follow the accepted business rules. Test function names carry the T identifiers. Parameterized inputs count as separate executed cases. The local result is in [local-check.log](evidence/R2-01/local-check.log).

| R1 scenario | R2 tests | Expected observation |
|---|---|---|
| AC-01, valid creation | T01, T09, T19 | A owns a quantity-two pending order and sequence-zero creation event. Opening a new connection preserves both. |
| AC-02, input boundaries | T02, T03 | 1 and 99, empty and 500-character notes succeed. Rejected requests leave both tables unchanged. The persisted service name comes from the catalogue. |
| AC-03, visibility | T04–T08, T12 | Two customers have independent lists. Unknown and inaccessible details share the same error. Staff can read both customers' histories. T20 will exercise the interface. |
| AC-04, normal lifecycle | T09, T10 | Four staff actions produce version four and five ordered events. READY_FOR_PICKUP precedes physical handover. |
| AC-05, denied operations | T11–T13, T18 | Rejected transitions preserve the full snapshot. Two orders retain isolated versions and event actors. |
| AC-06, transaction failure | T15, T16 | A real PostgreSQL trigger interrupts before history insertion or at deferred commit. A separate connection sees the original order and events. |
| AC-07, concurrent staff | T14, T17 | The update based on an old version returns STALE_VERSION, including when two connections reach the row lock together. |
| AC-08, reproducibility and user judgement | Local check script and GitHub workflow | Local execution is recorded. PR execution, deployed UI observation and VAL-01 remain pending. |

The three key run records are [JUnit results](evidence/R2-01/junit.xml), [fault and race output](evidence/R2-01/local-check.log) and [test sensitivity](evidence/R2-01/negative-control.log). T20 and VAL-01 refer to the future application interface. T21–T28 apply to the separately approved change after V1.0 release.

## Human review

Use the manual exercise in the [README](../README.md). Record the candidate ID, what you tried, what you observed, any concern and the reason for your decision. A later repository commit or PR run should identify the exact revision it checked.
