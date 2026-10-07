-- 股票价值投资财报分析软件 V1.0 - SQLite schema
-- 一个项目对应一个 .db 文件，包含该公司所有年度数据
-- 所有数值最终以"元"为统一单位存储

PRAGMA foreign_keys = ON;

-- 公司信息（每个项目唯一一家公司）
CREATE TABLE IF NOT EXISTS company (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    stock_code TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 年报元数据
CREATE TABLE IF NOT EXISTS year_report (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    pdf_path TEXT NOT NULL,
    is_annual_report INTEGER NOT NULL DEFAULT 1,
    report_title TEXT DEFAULT '',
    is_scanned INTEGER NOT NULL DEFAULT 0,
    parse_warnings TEXT DEFAULT '',  -- JSON 数组
    UNIQUE(company_id, year),
    FOREIGN KEY(company_id) REFERENCES company(id) ON DELETE CASCADE
);

-- 科目数据（每行：一个年度+一个报表+一个科目）
CREATE TABLE IF NOT EXISTS line_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    year INTEGER NOT NULL,
    statement_type TEXT NOT NULL,  -- "合并资产负债表" / "合并利润表" / "合并现金流量表"
    name TEXT NOT NULL,             -- 标准科目名
    original_value REAL,            -- PDF 原始识别值（按原始单位）
    modified_value REAL,            -- 用户修正值（按原始单位）
    unit TEXT NOT NULL DEFAULT '元',
    source_pdf TEXT DEFAULT '',
    source_page INTEGER DEFAULT 0,
    is_recognized INTEGER NOT NULL DEFAULT 1,  -- 0 表示未识别，UI 显示 ⚠
    UNIQUE(company_id, year, statement_type, name),
    FOREIGN KEY(company_id) REFERENCES company(id) ON DELETE CASCADE
);

-- 规则结果（每行：一个年度+一条规则）
CREATE TABLE IF NOT EXISTS rule_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    year INTEGER NOT NULL,
    actual_value REAL,           -- 实际值（比率类为小数，金额类为元）
    reference_value TEXT,        -- 参考值文字描述
    status TEXT NOT NULL,        -- RuleStatus.value
    conclusion TEXT NOT NULL,
    is_calculable INTEGER NOT NULL DEFAULT 1,
    course_source TEXT DEFAULT '',
    rules_version TEXT NOT NULL DEFAULT '1.0',
    computed_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(company_id, rule_id, year, rules_version),
    FOREIGN KEY(company_id) REFERENCES company(id) ON DELETE CASCADE
);

-- 项目元数据
CREATE TABLE IF NOT EXISTS project_meta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL UNIQUE,
    rules_version TEXT NOT NULL DEFAULT '1.0',
    app_version TEXT NOT NULL DEFAULT '1.0',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(company_id) REFERENCES company(id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_line_item_year ON line_item(company_id, year);
CREATE INDEX IF NOT EXISTS idx_line_item_statement ON line_item(company_id, statement_type);
CREATE INDEX IF NOT EXISTS idx_rule_result_rule ON rule_result(company_id, rule_id);
CREATE INDEX IF NOT EXISTS idx_year_report_company ON year_report(company_id, year);
