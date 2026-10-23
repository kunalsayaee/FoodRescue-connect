DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('donor', 'ngo')),
    organization  TEXT,
    phone         TEXT,
    city          TEXT,
    lat           REAL,
    lng           REAL,
    created_at    TEXT NOT NULL
);

CREATE TABLE listings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id      INTEGER NOT NULL REFERENCES users (id),
    title         TEXT NOT NULL,
    food_type     TEXT NOT NULL,
    is_veg        INTEGER NOT NULL DEFAULT 1,
    servings      INTEGER NOT NULL CHECK (servings > 0),
    address       TEXT NOT NULL,
    lat           REAL,
    lng           REAL,
    prepared_at   TEXT NOT NULL,
    expires_at    TEXT NOT NULL,
    notes         TEXT,
    status        TEXT NOT NULL DEFAULT 'posted'
                  CHECK (status IN ('posted', 'claimed', 'picked_up', 'delivered', 'expired', 'cancelled')),
    claimed_by    INTEGER REFERENCES users (id),
    claimed_at    TEXT,
    picked_up_at  TEXT,
    delivered_at  TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX idx_listings_status_expiry ON listings (status, expires_at);
CREATE INDEX idx_listings_donor ON listings (donor_id);
CREATE INDEX idx_listings_claimed_by ON listings (claimed_by);
