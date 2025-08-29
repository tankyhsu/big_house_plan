PRAGMA journal_mode = WAL;

PRAGMA foreign_keys = ON;

CREATE TABLE
  IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE
  IF NOT EXISTS category (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sub_name TEXT NOT NULL,
    target_units REAL NOT NULL,
    UNIQUE (name, sub_name)
  );

CREATE TABLE
  IF NOT EXISTS instrument (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT UNIQUE,
    name TEXT,
    type TEXT,
    currency TEXT,
    category_id INTEGER NOT NULL,
    active INTEGER DEFAULT 1,
    FOREIGN KEY (category_id) REFERENCES category (id)
  );

CREATE TABLE
  IF NOT EXISTS txn (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    action TEXT NOT NULL,
    shares REAL DEFAULT 0,
    price REAL DEFAULT 0,
    amount REAL,
    fee REAL DEFAULT 0,
    notes TEXT,
    group_id INTEGER
  );

CREATE TABLE
  IF NOT EXISTS price_eod (
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    close REAL NOT NULL,
    pre_close REAL,
    open REAL,
    high REAL,
    low REAL,
    vol REAL,
    amount REAL,
    PRIMARY KEY (ts_code, trade_date)
  );

CREATE TABLE
  IF NOT EXISTS ma_cache (
    ts_code TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    ma20 REAL,
    ma60 REAL,
    ma200 REAL,
    PRIMARY KEY (ts_code, trade_date)
  );

CREATE TABLE
  IF NOT EXISTS position(
    ts_code TEXT PRIMARY KEY,
    shares REAL NOT NULL DEFAULT 0,
    avg_cost REAL NOT NULL DEFAULT 0,
    last_update TEXT
  );

CREATE TABLE
  IF NOT EXISTS portfolio_daily (
    trade_date TEXT NOT NULL,
    ts_code TEXT NOT NULL,
    market_value REAL NOT NULL,
    cost REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    ret REAL,
    category_id INTEGER,
    PRIMARY KEY (trade_date, ts_code)
  );

CREATE TABLE
  IF NOT EXISTS category_daily (
    trade_date TEXT NOT NULL,
    category_id INTEGER NOT NULL,
    market_value REAL NOT NULL,
    cost REAL NOT NULL,
    pnl REAL NOT NULL,
    ret REAL,
    actual_units REAL,
    gap_units REAL,
    overweight INTEGER DEFAULT 0,
    PRIMARY KEY (trade_date, category_id)
  );

CREATE TABLE
  IF NOT EXISTS signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    ts_code TEXT,
    category_id INTEGER,
    level TEXT,
    type TEXT,
    message TEXT
  );