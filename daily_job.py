"""Daily Trade Buddy job."""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Dict

import pandas as pd

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


def parse_trade_date(file_name: str, modified_time: str | None) -> dt.date:
    """Derive the trade date using the filename or Drive metadata."""
    match = re.search(r"(\d{2})_(\d{2})_(\d{4})", file_name)
    if match:
        month, day, year = map(int, match.groups())
        return dt.date(year, month, day)
    if modified_time:
        normalized = modified_time.replace("Z", "+00:00")
        return dt.datetime.fromisoformat(normalized).date()
    return dt.date.today()


def process_file(
    *,
    file_meta: Dict[str, str],
    drive_client: DriveClient,
    db: Database,
    gemini: GeminiClient,
    email_client: EmailClient,
) -> None:
    file_id = file_meta["id"]
    file_name = file_meta["name"]
    LOGGER.info("Processing raw file %s (%s)", file_name, file_id)
    trade_date = parse_trade_date(file_name, file_meta.get("modifiedTime"))
    db.record_raw_file(
        drive_file_id=file_id,
        file_name=file_name,
        trade_date=trade_date.isoformat(),
    )

    local_csv = config.DOWNLOAD_DIR / f"{file_id}_{file_name}"
    drive_client.download_file(file_id, local_csv)
    trades_df = pd.read_csv(local_csv)

    report_text = gemini.generate_daily_report(trade_date, trades_df)
    html_report = render_html_report(
        title=f"Daily Trade Pulse - {trade_date:%b %d, %Y}",
        report_markdown=report_text,
        report_date=trade_date,
    )
    report_filename = f"daily_report_{trade_date.isoformat()}.md"
    report_path = config.DAILY_REPORTS_LOCAL_DIR / report_filename
    report_path.write_text(report_text, encoding="utf-8")
    html_filename = f"daily_report_{trade_date.isoformat()}.html"
    html_path = config.DAILY_REPORTS_LOCAL_DIR / html_filename
    html_path.write_text(html_report, encoding="utf-8")

    drive_report_id = drive_client.upload_file(
        report_path,
        config.DAILY_REPORTS_FOLDER_ID,
        "text/markdown",
        report_filename,
    )

    db.mark_raw_file_processed(file_id, drive_report_id)
    db.record_daily_report(
        drive_file_id=drive_report_id,
        file_name=report_filename,
        report_date=trade_date.isoformat(),
    )

    email_client.send_email(
        subject=f"Daily Trade Report - {trade_date:%Y-%m-%d}",
        body_text=report_text,
        html_body=html_report,
        attachments=[
            (
                html_filename,
                html_path.read_bytes(),
                "text/html",
            )
        ],
    )
    LOGGER.info("Finished processing %s", file_name)


def main() -> None:
    configure_logging()
    drive_client = DriveClient()
    db = Database(config.DB_PATH)
    gemini = GeminiClient(config.GEMINI_API_KEY)
    email_client = EmailClient()

    try:
        files = drive_client.list_files_in_folder(
            config.RAW_TRADES_FOLDER_ID,
            recursive=True,
        )
        csv_files = [
            f for f in files if f.get("name", "").lower().endswith(".csv")
        ]
        LOGGER.info("Found %d CSV files", len(csv_files))
        for file_meta in csv_files:
            if not db.raw_file_needs_processing(file_meta["id"]):
                continue
            try:
                process_file(
                    file_meta=file_meta,
                    drive_client=drive_client,
                    db=db,
                    gemini=gemini,
                    email_client=email_client,
                )
            except Exception:
                LOGGER.exception("Failed to process file %s", file_meta.get("name"))
    finally:
        db.close()


if __name__ == "__main__":
    main()



