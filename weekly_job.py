"""Weekly Trade Buddy job."""
from __future__ import annotations

import datetime as dt
import logging
from typing import List

import config
from db import Database
from drive_client import DriveClient
from email_client import EmailClient
from gemini_client import GeminiClient
from report_renderer import render_html_report

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def determine_target_week(reference: dt.date) -> tuple[int, int]:
    """Return iso (year, week) for the current week of *reference*."""
    iso = reference.isocalendar()
    return iso.year, iso.week


def fetch_daily_report_texts(rows, drive_client: DriveClient) -> List[str]:
    texts: List[str] = []
    for row in rows:
        local_path = config.DOWNLOAD_DIR / f"daily_{row['id']}.md"
        drive_client.download_file(row["drive_file_id"], local_path)
        texts.append(local_path.read_text(encoding="utf-8"))
    return texts


def main() -> None:
    configure_logging()
    today = dt.date.today()
    iso_year, iso_week = determine_target_week(today)
    week_start = dt.date.fromisocalendar(iso_year, iso_week, 1)
    week_end = week_start + dt.timedelta(days=6)

    drive_client = DriveClient()
    db = Database(config.DB_PATH)
    gemini = GeminiClient(config.GEMINI_API_KEY)
    email_client = EmailClient()

    try:
        rows = db.get_daily_reports_for_week(iso_year, iso_week)
        if not rows:
            LOGGER.info("No pending daily reports for ISO week %s-%02d", iso_year, iso_week)
            return
        daily_texts = fetch_daily_report_texts(rows, drive_client)
        weekly_text = gemini.generate_weekly_report(week_start, week_end, daily_texts)
        html_report = render_html_report(
            title=f"Weekly Trade Pulse - {week_start:%b %d} to {week_end:%b %d}",
            report_markdown=weekly_text,
            report_date=week_end,
        )

        filename = f"weekly_report_{iso_year}_{iso_week:02d}.md"
        report_path = config.WEEKLY_REPORTS_LOCAL_DIR / filename
        report_path.write_text(weekly_text, encoding="utf-8")
        html_filename = f"weekly_report_{iso_year}_{iso_week:02d}.html"
        html_path = config.WEEKLY_REPORTS_LOCAL_DIR / html_filename
        html_path.write_text(html_report, encoding="utf-8")

        drive_id = drive_client.upload_file(
            report_path,
            config.WEEKLY_REPORTS_FOLDER_ID,
            "text/markdown",
            filename,
        )

        db.record_weekly_report(
            drive_file_id=drive_id,
            file_name=filename,
            iso_year=iso_year,
            iso_week=iso_week,
            week_start_date=week_start.isoformat(),
            week_end_date=week_end.isoformat(),
        )
        db.mark_daily_reports_included([row["id"] for row in rows])

        email_client.send_email(
            subject=f"Weekly Trade Report - {week_start:%Y-%m-%d} to {week_end:%Y-%m-%d}",
            body_text=weekly_text,
            html_body=html_report,
            attachments=[(html_filename, html_path.read_bytes(), "text/html")],
        )
        LOGGER.info("Weekly report %s generated", filename)
    finally:
        db.close()


if __name__ == "__main__":
    main()

