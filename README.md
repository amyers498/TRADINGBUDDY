# Trade Buddy

Python 3.10+ toolkit that turns your Google Drive trade CSVs into daily, weekly, and monthly reports using Gemini, then emails and archives them. Designed for Raspberry Pi cron jobs; SQLite tracks processing state.

## Quick start
1) Install deps (preferably in a venv):
```
pip install pandas requests google-api-python-client google-auth google-auth-httplib2 google-auth-oauthlib markdown python-dotenv
```
2) Create `.env` in the repo root (see example below) and ensure `token.json`/`credentials.json` (OAuth) or service account JSON exist.
3) Run once to authorize Drive (opens a browser):
```
python daily_job.py
```
4) Set up cron (examples further down).

## Required environment variables
```
GOOGLE_OAUTH_CLIENT_SECRETS=credentials.json   # or GOOGLE_APPLICATION_CREDENTIALS for a service account
GOOGLE_OAUTH_TOKEN_FILE=token.json             # where OAuth token is cached
RAW_TRADES_FOLDER_ID=...                       # Drive folder for CSV uploads
DAILY_REPORTS_FOLDER_ID=...                    # Drive folder for daily reports
WEEKLY_REPORTS_FOLDER_ID=...                   # Drive folder for weekly reports
MONTHLY_REPORTS_FOLDER_ID=...                  # Drive folder for monthly reports

GEMINI_API_KEY=...                             # Gemini key
GEMINI_MODEL_NAME=gemini-2.5-pro               # default model

EMAIL_FROM=you@example.com
EMAIL_TO=you@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...

# Optional paths
TRADE_BUDDY_DB_PATH=trade_buddy.db
TRADE_BUDDY_DOWNLOAD_DIR=downloads
TRADE_BUDDY_REPORTS_DIR=reports
```

## How it works
- `daily_job.py`: finds new CSVs in `RAW_TRADES_FOLDER_ID`, generates markdown via Gemini, emails styled HTML (markdown attached), uploads markdown to Drive, and records state in SQLite.
- `weekly_job.py`: pulls daily reports for the current ISO week, summarizes to a weekly report, emails HTML, uploads markdown, marks daily reports included.
- `monthly_job.py`: pulls weekly reports for the current month, summarizes to a monthly report, emails HTML, uploads markdown, marks weekly reports included.
- `db.py`: SQLite schema and helpers.
- `drive_client.py`: OAuth/service account Drive helper.
- `email_client.py`: SMTP sender with text + HTML.
- `gemini_client.py`: prompt construction + API call.
- `report_renderer.py`: converts markdown to styled HTML for email.

## Cron examples (Eastern time)
Add to `crontab -e` (adjust paths/python as needed):
```
CRON_TZ=America/New_York

# Daily: every 5 minutes from 9:30pm–11:59pm ET
30-59/5 21 * * * cd /home/pi/TRADINGBUDDY && /usr/bin/env python3 daily_job.py >> logs/daily.log 2>&1
*/5 22-23 * * *   cd /home/pi/TRADINGBUDDY && /usr/bin/env python3 daily_job.py >> logs/daily.log 2>&1

# Weekly: Sundays at 9:00pm ET
0 21 * * 0 cd /home/pi/TRADINGBUDDY && /usr/bin/env python3 weekly_job.py >> logs/weekly.log 2>&1

# Monthly: last day of the month at 11:30pm ET
30 23 28-31 * * cd /home/pi/TRADINGBUDDY && [ "$(date -d tomorrow +\%d)" = 01 ] && /usr/bin/env python3 monthly_job.py >> logs/monthly.log 2>&1
```

## Testing locally
- `python daily_job.py` (requires a CSV in the Drive folder).
- `python weekly_job.py` / `python monthly_job.py` once daily data exists for the relevant period.

## Notes
- Reports uploaded to Drive are markdown for readability; emails include a styled HTML body/attachment.
- Update prompt tone/length in `gemini_client.py` and styling in `report_renderer.py` as desired.
