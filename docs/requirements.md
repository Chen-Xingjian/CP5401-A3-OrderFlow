# OrderFlow requirements

The accepted R1-01 baseline describes the needs of campus print-shop customers and staff. A customer needs to know when to wait and when to collect. Staff need to know which step has already been completed.

| Requirement | Observable outcome |
|---|---|
| FR-01 | A customer can order one active service in an integer quantity of 1–99 with an optional note of up to 500 characters. A successful request returns a unique order ID. |
| FR-02 | A customer can see their own orders, quantities, notes, service names, current stages and ordered histories. Another customer's order is absent from the list and inaccessible by ID. |
| FR-03 | Staff can read the shop queue, stages and histories for all customers. |
| FR-04 | Staff can confirm, start processing, mark ready for pickup and confirm physical handover in that order. |
| FR-05 | Each event records the actor, UTC time, source and target stage, and sequence. The full lifecycle has five events including creation. |

## Business rules

| Rules | Contract |
|---|---|
| BR-01, BR-04 | Derive ownership from the authenticated server-side principal. Resolve role and activity at the service boundary for every operation. Customer reads require ownership. Staff own the update permission. |
| BR-02 | Each request selects one available catalogue entry. Store its name at creation. Reject fractions, booleans, out-of-range quantities, invalid service IDs and oversized notes. |
| BR-03, BR-11 | PENDING → CONFIRMED → PROCESSING → READY_FOR_PICKUP → COMPLETED. The final edge records collection or handover. COMPLETED is terminal. |
| BR-05, BR-06, BR-07, BR-12 | The initial version and sequence are zero. One successful transition commits one new version and one event together. History is ordered by sequence. Its last target matches the order. |
| BR-08, BR-09 | An update carries the version the staff member read. Check access and version before the transition. An outdated version asks the caller to refresh. Rejections and rolled-back writes preserve the committed snapshot. |

Orders have one service each. Payments, shipping, inventory, uploads, order editing and catalogue management are outside the approved prototype. FR-06 and BR-10 describe prospective change CR001, customer cancellation. That change requires a released V1.0 and a separate decision.

## Quality targets

| ID | Measure |
|---|---|
| QR-01 | A fresh connection sees each committed order and history. Faults before history insertion or at commit leave the previous snapshot intact. |
| QR-02 | A different customer receives zero matching rows and a generic detail error. Each write checks the active account and its role. R3 must establish the identity through login. |
| QR-03 | Two staff connections using one version produce one commit and one refresh message. The history grows by exactly one. |
| QR-04 | The same check command runs on local and PR candidates. Preserve the actual result and revision identity. |
| QR-05 | Observe a customer distinguishing PROCESSING from READY_FOR_PICKUP and a staff member choosing the correct next action. Record misunderstandings and prompting during later user validation. |

## Database decisions for R2-01

PostgreSQL holds one row per order and one row per history event. The order and event share a transaction and timestamp. A primary key on order ID and sequence prevents duplicate sequence numbers. One ordered join reads an order and its history at a single statement snapshot. Each update locks only its target order for the version decision, under READ COMMITTED isolation. A second writer waits on that row, observes the committed version, then receives STALE_VERSION. Staff must confirm actual handover before recording COMPLETED.

The service accepts a trusted Principal carrying a user ID. It resolves the current role from the database. The acceptance harness constructs fictional principals directly. R3 owns login and session origin. For a storage error the service returns PERSISTENCE_ERROR with a refresh instruction. If a connection is lost during commit the client may need to read back the order to determine the outcome. The fault experiments in R2 exercise database-confirmed rollbacks.
