# Passport Status Tracker

A small FastAPI application for registering passport applications, simulating
status changes, and emailing applicants when their status changes.

## Project layout

```text
.
|-- main.py              # Routes and status-check workflow
|-- database.py          # MySQL engine and session setup
|-- models.py            # SQLAlchemy applications table
|-- notifications.py     # SMTP email delivery
|-- requirements.txt     # Python dependencies
|-- .env.example         # Configuration template
`-- templates/
    `-- index.html       # Dashboard with inline CSS and JavaScript
```

## How the application works

1. `GET /` reads applications from MySQL and renders the dashboard.
2. `POST /add-application` creates an application or updates its contact details.
3. A background loop automatically runs status checks at the configured interval.
4. `GET /admin` provides an administration dashboard for manual status updates.
5. A record is emailed only when `current_status` differs from `last_known_status`.
6. After detection, `last_known_status` is updated so the same change is not emailed again.

The lifecycle is:

```text
Application Submitted
  -> Document Verification
  -> Police Verification
  -> Passport Printed
  -> Dispatched
```

## Setup

Create the MySQL database in MySQL Workbench:

```sql
CREATE DATABASE IF NOT EXISTS passport_tracker
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

Create and activate the virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Copy the configuration template:

```powershell
Copy-Item .env.example .env
```

Automatic checks are enabled by default and run every 10 seconds. Configure them
in `.env` with `AUTOMATIC_CHECKS_ENABLED` and `STATUS_CHECK_INTERVAL_SECONDS`.
The minimum supported interval is 10 seconds.

For Gmail, enable two-step verification and place a Google App Password in
`SMTP_PASSWORD`. Placeholder addresses under `example.com`, `example.org`, and
`example.net` are skipped automatically.

Start the application:

```powershell
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000.

## Status lifecycle

The automatic monitor does not invent or randomly advance statuses. It detects
changes made through the admin dashboard or directly in the database. Each
distinct change produces at most one notification email.
