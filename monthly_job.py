"""Monthly Trade Buddy job."""
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


def previous_month(reference: dt.date) -> tuple[dt.date, dt.date]:
    """Return the date range covering the previous calendar month."""
    first_this_month = reference.replace(day=1)
    last_prev_month = first_this_month - dt.timedelta(days=1)
    first_prev_month = last_prev_month.replace(day=1)
    return first_prev_month, last_prev_month


def fetch_weekly_report_texts(rows, drive_client: DriveClient) -> List[str]:
    texts: List[str] = []
    for row in rows:
        local_path = config.DOWNLOAD_DIR / f"weekly_{row['id']}.md"
        drive_client.download_file(row["drive_file_id"], local_path)
        texts.append(local_path.read_text(encoding="utf-8"))
    return texts


def main() -> None:
    configure_logging()
    today = dt.date.today()
    month_start, month_end = previous_month(today)

    drive_client = DriveClient()
    db = Database(config.DB_PATH)
    gemini = GeminiClient(config.GEMINI_API_KEY)
    email_client = EmailClient()

    try:
        rows = db.get_weekly_reports_for_month(month_start.year, month_start.month)
        if not rows:
            LOGGER.info(
                "No weekly reports pending for %s-%02d",
                month_start.year,
                month_start.month,
            )
            return
        weekly_texts = fetch_weekly_report_texts(rows, drive_client)
        monthly_text = gemini.generate_monthly_report(month_start, month_end, weekly_texts)
        html_report = render_html_report(
            title=f"Monthly Trade Pulse – {month_start:%B %Y}",
            report_markdown=monthly_text,
            report_date=month_end,
        )

        filename = f"monthly_report_{month_start:%Y_%m}.md"
        report_path = config.MONTHLY_REPORTS_LOCAL_DIR / filename
        report_path.write_text(monthly_text, encoding="utf-8")

        drive_id = drive_client.upload_file(
            report_path,
            config.MONTHLY_REPORTS_FOLDER_ID,
            "text/markdown",
            filename,
        )

        db.record_monthly_report(
            drive_file_id=drive_id,
            file_name=filename,
            year=month_start.year,
            month=month_start.month,
            month_start=month_start.isoformat(),
            month_end=month_end.isoformat(),
        )
        db.mark_weekly_reports_included([row["id"] for row in rows])

        email_client.send_email(
            subject=f"Monthly Trade Report - {month_start:%B %Y}",
            body_text=monthly_text,
            html_body=html_report,
            attachments=[(filename, report_path.read_bytes(), "text/markdown")],
        )
        LOGGER.info("Monthly report %s uploaded as %s", filename, drive_id)
    finally:
        db.close()


if __name__ == "__main__":
    main()
