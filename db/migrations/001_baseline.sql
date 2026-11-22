CREATE TABLE users (
    id text NOT NULL PRIMARY KEY,
    username text NOT NULL UNIQUE,
    role text NOT NULL CHECK (role IN ('CUSTOMER', 'STAFF')),
    active integer NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE service_catalogue (
    id text NOT NULL PRIMARY KEY,
    name text NOT NULL CHECK (length(name) > 0),
    active integer NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE orders (
    id text NOT NULL PRIMARY KEY,
    owner_id text NOT NULL REFERENCES users(id),
    service_id text NOT NULL REFERENCES service_catalogue(id),
    service_name_snapshot text NOT NULL,
    quantity integer NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 99),
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 500),
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED')),
    version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at text NOT NULL,
    updated_at text NOT NULL,
    CHECK (updated_at >= created_at)
);

CREATE INDEX orders_owner_created_idx ON orders (owner_id, created_at DESC, id);

CREATE TABLE order_history (
    order_id text NOT NULL REFERENCES orders(id),
    sequence integer NOT NULL CHECK (sequence >= 0),
    from_status text CHECK (from_status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED')),
    to_status text NOT NULL CHECK (to_status IN ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED')),
    actor_id text NOT NULL REFERENCES users(id),
    occurred_at text NOT NULL,
    PRIMARY KEY (order_id, sequence),
    CHECK ((sequence = 0 AND from_status IS NULL AND to_status = 'PENDING')
        OR (sequence > 0 AND from_status IS NOT NULL AND from_status <> to_status))
);

INSERT INTO service_catalogue (id, name, active) VALUES
    ('bw-print', 'Black and white printing', true),
    ('colour-print', 'Colour printing', true),
    ('binding', 'Binding', false);
