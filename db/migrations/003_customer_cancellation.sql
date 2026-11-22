-- All steps run inside the migration writer transaction with foreign keys enabled.
ALTER TABLE order_history RENAME TO order_history_v10;
ALTER TABLE orders RENAME TO orders_v10;

CREATE TABLE orders (
    id text NOT NULL PRIMARY KEY,
    owner_id text NOT NULL REFERENCES users(id),
    service_id text NOT NULL REFERENCES service_catalogue(id),
    service_name_snapshot text NOT NULL,
    quantity integer NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 99),
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 500),
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED', 'CANCELLED')),
    version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at text NOT NULL,
    updated_at text NOT NULL,
    CHECK (updated_at >= created_at)
);

CREATE TABLE order_history (
    order_id text NOT NULL REFERENCES orders(id),
    sequence integer NOT NULL CHECK (sequence >= 0),
    from_status text CHECK (from_status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED', 'CANCELLED')),
    to_status text NOT NULL CHECK (to_status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED', 'CANCELLED')),
    actor_id text NOT NULL REFERENCES users(id),
    occurred_at text NOT NULL,
    PRIMARY KEY (order_id, sequence),
    CHECK ((sequence = 0 AND from_status IS NULL AND to_status = 'PENDING')
        OR (sequence > 0 AND from_status IS NOT NULL AND from_status <> to_status))
);

INSERT INTO orders (id, owner_id, service_id, service_name_snapshot, quantity, note,
                    status, version, created_at, updated_at)
SELECT id, owner_id, service_id, service_name_snapshot, quantity, note,
       status, version, created_at, updated_at FROM orders_v10;

INSERT INTO order_history (order_id, sequence, from_status, to_status, actor_id, occurred_at)
SELECT order_id, sequence, from_status, to_status, actor_id, occurred_at FROM order_history_v10;

DROP TABLE order_history_v10;
DROP TABLE orders_v10;
CREATE INDEX orders_owner_created_idx ON orders (owner_id, created_at DESC, id);
