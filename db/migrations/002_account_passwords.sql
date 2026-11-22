CREATE TABLE account_passwords (
    user_id text PRIMARY KEY REFERENCES users(id),
    salt blob NOT NULL CHECK (length(salt) = 16),
    digest blob NOT NULL CHECK (length(digest) = 32)
);
