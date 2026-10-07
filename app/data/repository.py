# -*- coding: utf-8 -*-
"""
SQLite 持久化层 - 把 AnalysisProject 保存到 .db 文件 / 从 .db 文件加载。

设计要点：
1. 一个 .db 文件对应一个 AnalysisProject（一家公司所有年度数据）
2. 所有数值统一以"元"为单位存储（LineItem.value_in_yuan 已在调用方完成转换，本层只持久化 original_value/modified_value 与 unit）
3. SQLite 查询全部使用 ? 占位符参数化，不拼接字符串
4. 重复保存时先清空旧数据再写入（实现"覆盖更新"语义）
"""
import json
import sqlite3
from pathlib import Path
from typing import List

from app.config import APP_VERSION, SCHEMA_FILE
from app.models.company import Company
from app.models.line_item import LineItem
from app.models.project import AnalysisProject
from app.models.rule import RuleResult, RuleStatus
from app.models.statements import YearReport


def save_project(project: AnalysisProject, db_path: str) -> None:
    """
    把 project 保存到 SQLite 文件。
    - 若文件不存在则创建（先执行 schema.sql）
    - 已存在的项目数据先清空再写入（避免重复）
    - 所有 LineItem 按 (year, statement_type, name) 唯一
    - 所有 RuleResult 按 (rule_id, year, rules_version) 唯一
    - 使用参数化查询，不用字符串拼接
    """
    db_path = str(db_path)
    # sqlite3.connect 在文件不存在时会自动创建空文件
    conn = sqlite3.connect(db_path)
    try:
        _init_db(conn)

        # 清空旧数据（按 FK 依赖顺序：子表先于父表）
        # schema.sql 中开启了 PRAGMA foreign_keys = ON，
        # 因此必须按 line_item -> rule_result -> year_report -> project_meta -> company 的顺序删除
        for table in ("line_item", "rule_result", "year_report", "project_meta", "company"):
            conn.execute(f"DELETE FROM {table}")

        # 插入 company，拿到自增 id
        cur = conn.execute(
            "INSERT INTO company (name, stock_code) VALUES (?, ?)",
            (project.company.name, project.company.stock_code),
        )
        company_id = cur.lastrowid

        # 插入 year_report
        for yr in project.year_reports:
            conn.execute(
                "INSERT INTO year_report "
                "(company_id, year, pdf_path, is_annual_report, report_title, is_scanned, parse_warnings) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    company_id,
                    yr.year,
                    yr.pdf_path,
                    1 if yr.is_annual_report else 0,
                    yr.report_title,
                    1 if yr.is_scanned else 0,
                    json.dumps(yr.parse_warnings, ensure_ascii=False),
                ),
            )

        # 插入 line_item（aliases 不持久化，schema 中无对应列）
        for li in project.line_items:
            conn.execute(
                "INSERT INTO line_item "
                "(company_id, year, statement_type, name, original_value, modified_value, "
                "unit, source_pdf, source_page, is_recognized) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    company_id,
                    li.year,
                    li.statement_type,
                    li.name,
                    li.original_value,
                    li.modified_value,
                    li.unit,
                    li.source_pdf,
                    li.source_page,
                    1 if li.is_recognized else 0,
                ),
            )

        # 插入 rule_result（evidence 不持久化，schema 中无对应列）
        for rr in project.rule_results:
            conn.execute(
                "INSERT INTO rule_result "
                "(company_id, rule_id, rule_name, year, actual_value, reference_value, "
                "status, conclusion, is_calculable, course_source, rules_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    company_id,
                    rr.rule_id,
                    rr.rule_name,
                    rr.year,
                    rr.actual_value,
                    rr.reference_value,
                    rr.status.value,
                    rr.conclusion,
                    1 if rr.is_calculable else 0,
                    rr.course_source,
                    project.rules_version,
                ),
            )

        # 插入 project_meta
        conn.execute(
            "INSERT OR REPLACE INTO project_meta (company_id, rules_version, app_version) "
            "VALUES (?, ?, ?)",
            (company_id, project.rules_version, APP_VERSION),
        )

        conn.commit()
    finally:
        conn.close()


def load_project(db_path: str) -> AnalysisProject:
    """
    从 SQLite 文件加载项目。
    - 文件不存在抛 FileNotFoundError
    - 重建 Company / YearReport[] / LineItem[] / RuleResult[] 对象
    - rules_version 从 project_meta 读
    """
    if not Path(db_path).exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # company
        row = conn.execute(
            "SELECT name, stock_code FROM company LIMIT 1"
        ).fetchone()
        if row is None:
            raise ValueError("No company record in database")
        company = Company(name=row["name"], stock_code=row["stock_code"] or "")

        # year_report
        year_reports: List[YearReport] = []
        for r in conn.execute(
            "SELECT year, pdf_path, is_annual_report, report_title, is_scanned, parse_warnings "
            "FROM year_report ORDER BY year"
        ):
            warnings_raw = r["parse_warnings"]
            warnings = json.loads(warnings_raw) if warnings_raw else []
            year_reports.append(
                YearReport(
                    year=r["year"],
                    pdf_path=r["pdf_path"] or "",
                    company=company,
                    is_annual_report=bool(r["is_annual_report"]),
                    report_title=r["report_title"] or "",
                    is_scanned=bool(r["is_scanned"]),
                    parse_warnings=warnings,
                )
            )

        # line_item
        line_items: List[LineItem] = []
        for r in conn.execute(
            "SELECT year, statement_type, name, original_value, modified_value, "
            "unit, source_pdf, source_page, is_recognized FROM line_item"
        ):
            line_items.append(
                LineItem(
                    year=r["year"],
                    statement_type=r["statement_type"],
                    name=r["name"],
                    aliases=[],  # aliases 不持久化
                    original_value=r["original_value"],
                    modified_value=r["modified_value"],
                    unit=r["unit"] or "元",
                    source_pdf=r["source_pdf"] or "",
                    source_page=r["source_page"] or 0,
                    is_recognized=bool(r["is_recognized"]),
                )
            )

        # rule_result
        rule_results: List[RuleResult] = []
        for r in conn.execute(
            "SELECT rule_id, rule_name, year, actual_value, reference_value, "
            "status, conclusion, is_calculable, course_source FROM rule_result"
        ):
            status_str = r["status"]
            try:
                status = RuleStatus(status_str)
            except ValueError:
                status = RuleStatus.NOT_APPLICABLE
            rule_results.append(
                RuleResult(
                    rule_id=r["rule_id"],
                    rule_name=r["rule_name"],
                    year=r["year"],
                    actual_value=r["actual_value"],
                    reference_value=r["reference_value"] or "",
                    status=status,
                    conclusion=r["conclusion"] or "",
                    evidence=[],  # evidence 不持久化
                    course_source=r["course_source"] or "",
                    is_calculable=bool(r["is_calculable"]),
                )
            )

        # project_meta
        rules_version = "1.0"
        meta_row = conn.execute(
            "SELECT rules_version FROM project_meta LIMIT 1"
        ).fetchone()
        if meta_row is not None:
            rules_version = meta_row["rules_version"] or "1.0"

        return AnalysisProject(
            company=company,
            year_reports=year_reports,
            line_items=line_items,
            rule_results=rule_results,
            rules_version=rules_version,
        )
    finally:
        conn.close()


def _init_db(conn: sqlite3.Connection) -> None:
    """执行 schema.sql 初始化表结构"""
    conn.executescript(_get_schema_sql())


def _get_schema_sql() -> str:
    """读取 schema.sql 内容"""
    return SCHEMA_FILE.read_text(encoding="utf-8")
