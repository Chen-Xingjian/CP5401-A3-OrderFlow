CREATE TABLE users (
    id text PRIMARY KEY,
    username text NOT NULL UNIQUE,
    role text NOT NULL CHECK (role IN ('CUSTOMER', 'STAFF')),
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE service_catalogue (
    id text PRIMARY KEY,
    name text NOT NULL CHECK (length(name) > 0),
    active boolean NOT NULL DEFAULT true
);

CREATE TYPE order_status AS ENUM ('PENDING', 'CONFIRMED', 'PROCESSING', 'READY_FOR_PICKUP', 'COMPLETED');

CREATE TABLE orders (
    id uuid PRIMARY KEY,
    owner_id text NOT NULL REFERENCES users(id),
    service_id text NOT NULL REFERENCES service_catalogue(id),
    service_name_snapshot text NOT NULL,
    quantity integer NOT NULL CHECK (quantity BETWEEN 1 AND 99),
    note text NOT NULL DEFAULT '' CHECK (char_length(note) <= 500),
    status order_status NOT NULL DEFAULT 'PENDING',
    version integer NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL,
    CHECK (updated_at >= created_at)
);

CREATE INDEX orders_owner_created_idx ON orders (owner_id, created_at DESC, id);

CREATE TABLE order_history (
    order_id uuid NOT NULL REFERENCES orders(id),
    sequence integer NOT NULL CHECK (sequence >= 0),
    from_status order_status,
    to_status order_status NOT NULL,
    actor_id text NOT NULL REFERENCES users(id),
    occurred_at timestamptz NOT NULL,
    PRIMARY KEY (order_id, sequence),
    CHECK ((sequence = 0 AND from_status IS NULL AND to_status = 'PENDING')
        OR (sequence > 0 AND from_status IS NOT NULL AND from_status <> to_status))
);

INSERT INTO service_catalogue (id, name, active) VALUES
    ('bw-print', 'Black and white printing', true),
    ('colour-print', 'Colour printing', true),
    ('binding', 'Binding', false);
