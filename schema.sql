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
    group_id INTEGER,
    realized_pnl REAL
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
    last_update TEXT,
    opening_date TEXT
  );

-- portfolio_daily and category_daily tables removed
-- All portfolio and category data is now calculated dynamically from:
-- - position table (current holdings)
-- - price_eod table (price data)
-- This simplifies the data model and ensures single source of truth

CREATE TABLE
  IF NOT EXISTS signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    ts_code TEXT,
    category_id INTEGER,
    scope_type TEXT DEFAULT 'INSTRUMENT',
    scope_data TEXT,
    level TEXT,
    type TEXT,
    message TEXT
  );

-- 自选关注（Watchlist）：用于管理想要关注但未必持仓的标的
-- 仅关联 instrument.ts_code，不参与类别目标/再平衡等计算
CREATE TABLE
  IF NOT EXISTS watchlist (
    ts_code TEXT PRIMARY KEY,
    note TEXT,
    created_at TEXT DEFAULT (datetime('now'))
  );

CREATE TABLE
  IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    request_id TEXT,
    before_json TEXT,
    after_json TEXT,
    payload_json TEXT,
    result TEXT,
    err_msg TEXT,
    latency_ms INTEGER
  );

-- 索引用于提高日志查询性能
CREATE INDEX IF NOT EXISTS idx_log_ts ON operation_log(ts);
CREATE INDEX IF NOT EXISTS idx_log_action ON operation_log(action);

-- 信号表说明：
-- 存储历史交易信号，每个标的每种信号类型在特定日期只能有一条记录
-- trade_date: 信号首次触发的日期 (YYYY-MM-DD格式)
-- ts_code: 标的代码 (与instrument.ts_code关联)
-- category_id: 类别ID (与category.id关联，用于类别级信号)
-- level: 信号级别 (HIGH/MEDIUM/LOW/INFO)
-- type: 信号类型 (STOP_GAIN/STOP_LOSS/BUY_SIGNAL/SELL_SIGNAL/REBALANCE/RISK_ALERT等)
-- message: 信号描述信息
--
-- 重要：信号记录是历史性的，不应在重新计算时被清除
-- calc_svc中的insert_signal_instrument/insert_signal_category会自动去重
