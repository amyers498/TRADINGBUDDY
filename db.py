"""SQLite database helpers for Trade Buddy."""
from __future__ import annotations

import datetime as dt
import sqlite3
from pathlib import Path
from typing import Iterable, List, Sequence


class Database:
    """Lightweight wrapper around sqlite3 for persisting processing state."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def close(self) -> None:
        """Close the connection."""
        self.conn.close()

    def _ensure_tables(self) -> None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_files (
                id INTEGER PRIMARY KEY,
                drive_file_id TEXT UNIQUE,
                file_name TEXT,
                trade_date TEXT,
                daily_report_drive_id TEXT,
                processed_at TEXT
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY,
                drive_file_id TEXT UNIQUE,
                file_name TEXT,
                report_date TEXT,
                included_in_weekly INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY,
                drive_file_id TEXT UNIQUE,
                file_name TEXT,
                iso_year INTEGER,
                iso_week INTEGER,
                week_start_date TEXT,
                week_end_date TEXT,
                included_in_monthly INTEGER DEFAULT 0
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS monthly_reports (
                id INTEGER PRIMARY KEY,
                drive_file_id TEXT UNIQUE,
                file_name TEXT,
                year INTEGER,
                month INTEGER,
                month_start TEXT,
                month_end TEXT
            )
            """
        )
        self.conn.commit()

    def record_raw_file(
        self,
        *,
        drive_file_id: str,
        file_name: str,
        trade_date: str,
        daily_report_drive_id: str | None = None,
    ) -> None:
        """Insert or update a raw trade file entry."""
        processed_at = dt.datetime.utcnow().isoformat() if daily_report_drive_id else None
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO raw_files (drive_file_id, file_name, trade_date, daily_report_drive_id, processed_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(drive_file_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    trade_date=excluded.trade_date,
                    daily_report_drive_id=excluded.daily_report_drive_id,
                    processed_at=COALESCE(excluded.processed_at, raw_files.processed_at)
                """,
                (drive_file_id, file_name, trade_date, daily_report_drive_id, processed_at),
            )

    def mark_raw_file_processed(self, drive_file_id: str, daily_report_drive_id: str) -> None:
        """Mark a raw file as processed."""
        processed_at = dt.datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                "UPDATE raw_files SET daily_report_drive_id=?, processed_at=? WHERE drive_file_id=?",
                (daily_report_drive_id, processed_at, drive_file_id),
            )

    def raw_file_needs_processing(self, drive_file_id: str) -> bool:
        """Return True when a raw file is missing its daily report id."""
        cursor = self.conn.execute(
            "SELECT daily_report_drive_id FROM raw_files WHERE drive_file_id=?",
            (drive_file_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return True
        return row["daily_report_drive_id"] is None

    def get_raw_files_pending_processing(self) -> List[sqlite3.Row]:
        """Return raw files that still need daily report generation."""
        cursor = self.conn.execute(
            "SELECT * FROM raw_files WHERE daily_report_drive_id IS NULL"
        )
        return list(cursor.fetchall())

    def record_daily_report(
        self,
        *,
        drive_file_id: str,
        file_name: str,
        report_date: str,
    ) -> None:
        """Insert or update a daily report row."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO daily_reports (drive_file_id, file_name, report_date)
                VALUES (?, ?, ?)
                ON CONFLICT(drive_file_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    report_date=excluded.report_date
                """,
                (drive_file_id, file_name, report_date),
            )

    def get_daily_reports_for_week(self, iso_year: int, iso_week: int) -> List[sqlite3.Row]:
        """Return pending daily reports for the requested ISO week."""
        cursor = self.conn.execute(
            "SELECT * FROM daily_reports WHERE included_in_weekly = 0"
        )
        rows = []
        for row in cursor.fetchall():
            report_date = dt.date.fromisoformat(row["report_date"])
            row_year, row_week, _ = report_date.isocalendar()
            if row_year == iso_year and row_week == iso_week:
                rows.append(row)
        return rows

    def mark_daily_reports_included(self, report_ids: Sequence[int]) -> None:
        """Mark daily reports as consumed by a weekly summary."""
        if not report_ids:
            return
        with self.conn:
            self.conn.executemany(
                "UPDATE daily_reports SET included_in_weekly = 1 WHERE id = ?",
                [(rid,) for rid in report_ids],
            )

    def record_weekly_report(
        self,
        *,
        drive_file_id: str,
        file_name: str,
        iso_year: int,
        iso_week: int,
        week_start_date: str,
        week_end_date: str,
    ) -> None:
        """Insert or update a weekly report record."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO weekly_reports (
                    drive_file_id,
                    file_name,
                    iso_year,
                    iso_week,
                    week_start_date,
                    week_end_date
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(drive_file_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    iso_year=excluded.iso_year,
                    iso_week=excluded.iso_week,
                    week_start_date=excluded.week_start_date,
                    week_end_date=excluded.week_end_date
                """,
                (
                    drive_file_id,
                    file_name,
                    iso_year,
                    iso_week,
                    week_start_date,
                    week_end_date,
                ),
            )

    def get_weekly_reports_for_month(self, year: int, month: int) -> List[sqlite3.Row]:
        """Return weekly reports overlapping the requested month that are pending monthly inclusion."""
        month_start = dt.date(year, month, 1)
        if month == 12:
            month_end = dt.date(year + 1, 1, 1) - dt.timedelta(days=1)
        else:
            month_end = dt.date(year, month + 1, 1) - dt.timedelta(days=1)

        cursor = self.conn.execute(
            "SELECT * FROM weekly_reports WHERE included_in_monthly = 0"
        )
        rows = []
        for row in cursor.fetchall():
            week_start = dt.date.fromisoformat(row["week_start_date"])
            week_end = dt.date.fromisoformat(row["week_end_date"])
            if week_start <= month_end and week_end >= month_start:
                rows.append(row)
        return rows

    def mark_weekly_reports_included(self, report_ids: Iterable[int]) -> None:
        """Mark weekly reports as included in a monthly report."""
        ids = list(report_ids)
        if not ids:
            return
        with self.conn:
            self.conn.executemany(
                "UPDATE weekly_reports SET included_in_monthly = 1 WHERE id = ?",
                [(rid,) for rid in ids],
            )

    def record_monthly_report(
        self,
        *,
        drive_file_id: str,
        file_name: str,
        year: int,
        month: int,
        month_start: str,
        month_end: str,
    ) -> None:
        """Store metadata for a generated monthly report."""
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO monthly_reports (drive_file_id, file_name, year, month, month_start, month_end)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(drive_file_id) DO UPDATE SET
                    file_name=excluded.file_name,
                    year=excluded.year,
                    month=excluded.month,
                    month_start=excluded.month_start,
                    month_end=excluded.month_end
                """,
                (drive_file_id, file_name, year, month, month_start, month_end),
            )
