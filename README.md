# Passport Tracking System

A web-based passport application tracker built with FastAPI and MySQL. Users can register an application, view its current status, and receive an email when the status changes. Administrators can manage each application through a dedicated dashboard.

## Features

- Register and update passport applicant details
- Track applications through a five-stage lifecycle
- Manage application statuses from an admin dashboard
- Detect status changes automatically in the background
- Send one email notification for each distinct status change
- Trigger a status check manually when required
- Keep database and email credentials outside the source code

## Status lifecycle

```text
Application Submitted
  -> Document Verification
  -> Police Verification
  -> Passport Printed
  -> Dispatched
```

## Technology stack

- **Backend:** Python, FastAPI, Uvicorn
- **Database:** MySQL, SQLAlchemy, aiomysql
- **Frontend:** Jinja2, HTML, CSS, JavaScript
- **Notifications:** SMTP email

## Project structure

```text
.
|-- main.py              # Routes and status-check workflow
|-- database.py          # Async MySQL engine and session setup
|-- models.py            # SQLAlchemy application model
|-- notifications.py     # SMTP email delivery
|-- requirements.txt     # Python dependencies
|-- .env.example         # Configuration template
`-- templates/
    |-- index.html       # User dashboard
    `-- admin.html       # Administration dashboard
```

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/hetvi213/Passport-Tracking-System.git
cd Passport-Tracking-System
```

### 2. Create the database

Run the following in MySQL Workbench or another MySQL client:

```sql
CREATE DATABASE IF NOT EXISTS passport_tracker
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

The application creates its required table automatically when it starts.

### 3. Create a virtual environment and install dependencies

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 4. Configure the application

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux, use `cp .env.example .env` instead. Then update `.env` with your MySQL and SMTP settings.

| Variable | Purpose | Example/default |
| --- | --- | --- |
| `DATABASE_URL` | Async MySQL connection string | `mysql+aiomysql://root:@localhost:3306/passport_tracker?charset=utf8mb4` |
| `AUTOMATIC_CHECKS_ENABLED` | Enables background status checks | `true` |
| `STATUS_CHECK_INTERVAL_SECONDS` | Delay between checks (minimum 10 seconds) | `10` |
| `SMTP_HOST` | SMTP server hostname | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP account username | Your email address |
| `SMTP_PASSWORD` | SMTP password or app password | Your app password |
| `SMTP_FROM` | Notification sender address | Your email address |
| `SMTP_USE_SSL` | Uses implicit SSL when set to `true` | `false` |

For Gmail, enable two-step verification and use a Google App Password for `SMTP_PASSWORD`. Never commit the local `.env` file.

### 5. Run the application

```powershell
python -m uvicorn main:app --reload
```

Open the following pages:

- User dashboard: <http://127.0.0.1:8000>
- Admin dashboard: <http://127.0.0.1:8000/admin>
- Interactive API documentation: <http://127.0.0.1:8000/docs>

## Main routes

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/` | Displays registered applications |
| `POST` | `/add-application` | Creates an application or updates its contact details |
| `GET` | `/admin` | Displays the administration dashboard |
| `POST` | `/admin/update-status` | Changes an application's status |
| `POST` | `/run-check` | Runs a status-change check manually |

## How notifications work

The background monitor compares an application's `current_status` with its `last_known_status`. When they differ, it sends an email and updates the stored known status, ensuring the same change generates at most one notification. The monitor detects updates made through the admin dashboard or directly in the database; it does not randomly advance applications.

## License

This project is available for educational and portfolio purposes.
