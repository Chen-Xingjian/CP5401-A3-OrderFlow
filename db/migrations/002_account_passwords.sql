CREATE TABLE account_passwords (
    user_id text PRIMARY KEY REFERENCES users(id),
    salt bytea NOT NULL CHECK (octet_length(salt) = 16),
    digest bytea NOT NULL CHECK (octet_length(digest) = 32)
);
