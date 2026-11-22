# OrderFlow requirements

The accepted R1-01 baseline describes the needs of campus print-shop customers and staff. A customer needs to know when to wait and when to collect. Staff need to know which step has already been completed.

| Requirement | Observable outcome |
|---|---|
| FR-01 | A customer can order one active service in an integer quantity of 1–99 with an optional note of up to 500 characters. A successful request returns a unique order ID. |
| FR-02 | A customer can see their own orders, quantities, notes, service names, current stages and ordered histories. Another customer's order is absent from the list and inaccessible by ID. |
| FR-03 | Staff can read the shop queue, stages and histories for all customers. |
| FR-04 | Staff can confirm, start processing, mark ready for pickup and confirm physical handover in that order. |
| FR-06 (V1.1) | An active customer can cancel an owned pending or confirmed order and see the cancellation in its history. |
| FR-05 | Each event records the actor, UTC time, source and target stage, and sequence. The full lifecycle has five events including creation. |

## Business rules

| Rules | Contract |
|---|---|
| BR-01, BR-04 | Derive ownership from the active principal selected in the fictional demo workspace. Resolve role and activity at the service boundary for every operation. Customer reads require ownership. Only staff may advance production and handover. |
| BR-02 | Each request selects one available catalogue entry. Store its name at creation. Reject fractions, booleans, out-of-range quantities, invalid service IDs and oversized notes. |
| BR-03, BR-11 | PENDING → CONFIRMED → PROCESSING → READY_FOR_PICKUP → COMPLETED. The final edge records collection or handover. COMPLETED is terminal. |
| BR-05, BR-06, BR-07, BR-12 | The initial version and sequence are zero. One successful transition commits one new version and one event together. History is ordered by sequence. Its last target matches the order. |
| BR-08, BR-09 | An update carries the version the acting user read. Check access and version before the transition. An outdated version asks the caller to refresh. Rejections and rolled-back writes preserve the committed snapshot. |

Orders have one service each. Payments, shipping, inventory, uploads, order editing and catalogue management are outside the approved prototype. The student approved [CR001](https://github.com/Chen-Xingjian/CP5401-OrderFlow/issues/2) after V1.0. Under BR-10/11 an active owner can move PENDING or CONFIRMED to CANCELLED. The service checks ownership before version and version before state. CANCELLED is terminal. A current-version retry reports ALREADY_CANCELLED; an old version reports STALE_VERSION. Both preserve the stored snapshot.

## Quality targets

| ID | Measure |
|---|---|
| QR-01 | A fresh connection sees each committed order and history. Faults before history insertion or at commit leave the previous snapshot intact. |
| QR-02 | A different customer receives zero matching rows and a generic detail error. Each write checks the active account and its role. R3 used password login. The student approved direct selection of four fictional identities for R4. Visitors can switch to staff, so the deployed database must contain demo data only. |
| QR-03 | Two staff connections using one version produce one commit and one refresh message. The history grows by exactly one. |
| QR-04 | The same check command runs on local and PR candidates. Preserve the actual result and revision identity. |
| QR-05 | Observe a customer distinguishing PROCESSING from READY_FOR_PICKUP and a staff member choosing the correct next action. Record misunderstandings and prompting during later user validation. |

## Database decisions for R2-01

PostgreSQL holds one row per order and one row per history event. The order and event share a transaction and timestamp. A primary key on order ID and sequence prevents duplicate sequence numbers. One ordered join reads an order and its history at a single statement snapshot. Each update locks only its target order for the version decision, under READ COMMITTED isolation. A second writer waits on that row, observes the committed version, then receives STALE_VERSION. Staff must confirm actual handover before recording COMPLETED.

The service accepts a trusted Principal carrying a user ID. It resolves the current role from the database. The acceptance harness constructs fictional principals directly. R4 selects the active fictional identity in the same Streamlit session. For a storage error the service returns PERSISTENCE_ERROR with a refresh instruction. If a connection is lost during commit the client may need to read back the order to determine the outcome. The fault experiments in R2 exercise database-confirmed rollbacks.

## R4 interaction change

The student approved a role selector followed by a per-role user selector on the same page. Customers Alex and Blair see their own orders. Staff Sam and Taylor share the queue and retain individual event attribution. Switching identity clears the previous selection, draft and action feedback. The change precedes V1.0 and is independent of CR001.

## R4-02 local storage revision

The student selected local SQLite for the demo. Each write uses BEGIN IMMEDIATE before checking the active identity and the displayed version. A second writer observes the newly committed version and receives STALE_VERSION. Local tests cover commit rollback and reopen the same file to check persistence. The R2 database choices above document the earlier PostgreSQL implementation.

## CR002 staff workload and overdue pickup

FR-07 / BR-13. Active staff see one count per open stage across all customers and a count of overdue pickups within the ready stage. On each render or refresh, compare the current instant with the recorded ready event. At 48 elapsed hours, including weekends, mark a still-ready order as **Pickup overdue** in the staff selector and detail. Display the ready time in Singapore time. Reading the queue preserves order versions and histories. A physical handover removes the order from both ready and overdue counts. Customers retain their own order views. [CR002](https://github.com/Chen-Xingjian/CP5401-OrderFlow/issues/6)
