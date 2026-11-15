-- Fridgemate database schema (SQLite). Created automatically on first run.
CREATE TABLE IF NOT EXISTS households (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    invite_code TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS members (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    household_id TEXT REFERENCES households(id),
    dietary_restrictions TEXT NOT NULL DEFAULT '[]',
    disliked_ingredients TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS credentials (
    account_id TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL REFERENCES households(id),
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    unit TEXT NOT NULL,
    original_amount REAL NOT NULL,
    location TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    added_on TEXT NOT NULL,
    owner_id TEXT REFERENCES members(id),
    expiry_estimated INTEGER NOT NULL DEFAULT 0,
    price TEXT,
    payer_id TEXT REFERENCES members(id),
    is_offered INTEGER NOT NULL DEFAULT 0,
    offered_by_id TEXT REFERENCES members(id)
);
CREATE INDEX IF NOT EXISTS items_household ON items(household_id);
CREATE TABLE IF NOT EXISTS shopping_items (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    member_id TEXT,
    name TEXT NOT NULL,
    amount REAL,
    unit TEXT,
    section TEXT NOT NULL,
    reasons TEXT NOT NULL DEFAULT '[]',
    checked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    price TEXT NOT NULL,
    payer_id TEXT NOT NULL,
    bought_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    household_id TEXT NOT NULL,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    amount TEXT NOT NULL,
    paid_on TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    message TEXT NOT NULL,
    item_id TEXT,
    kind TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meal_plans (
    id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data BLOB NOT NULL
);
