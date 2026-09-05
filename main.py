import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, Base, engine, get_db
from models import Application
from notifications import send_status_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("passport-tracker")

STATUS_LIFECYCLE = (
    "Application Submitted",
    "Document Verification",
    "Police Verification",
    "Passport Printed",
    "Dispatched",
)
AUTOMATIC_CHECKS_ENABLED = os.getenv("AUTOMATIC_CHECKS_ENABLED", "true").lower() == "true"
STATUS_CHECK_INTERVAL_SECONDS = max(
    10,
    int(os.getenv("STATUS_CHECK_INTERVAL_SECONDS", "60")),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def redirect_to_dashboard(message: str) -> RedirectResponse:
    query = urlencode({"message": message})
    return RedirectResponse(
        url=f"/?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def redirect_to_admin(message: str) -> RedirectResponse:
    query = urlencode({"message": message})
    return RedirectResponse(
        url=f"/admin?{query}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def automatic_status_check_loop() -> None:
    """Detect externally changed statuses while the server is active."""
    logger.info(
        "Automatic status checks enabled (every %d seconds)",
        STATUS_CHECK_INTERVAL_SECONDS,
    )
    while True:
        try:
            await run_status_check()
        except Exception:
            logger.exception("Automatic status check failed")
        await asyncio.sleep(STATUS_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create missing tables at startup and close the engine at shutdown."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    scheduler_task = None
    if AUTOMATIC_CHECKS_ENABLED:
        scheduler_task = asyncio.create_task(automatic_status_check_loop())

    try:
        yield
    finally:
        if scheduler_task is not None:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task
        await engine.dispose()


app = FastAPI(title="Passport Status Tracker", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).order_by(Application.last_updated.desc())
    applications = (await db.scalars(query)).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "applications": applications,
            "message": request.query_params.get("message"),
        },
    )


@app.post("/add-application")
async def add_application(
    file_no: str = Form(...),
    date_of_birth: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    normalized_file_no = file_no.strip().upper()
    application = await db.get(Application, normalized_file_no)

    if application is None:
        initial_status = STATUS_LIFECYCLE[0]
        application = Application(
            file_no=normalized_file_no,
            date_of_birth=date_of_birth.strip(),
            email=email.strip().lower(),
            phone=phone.strip(),
            current_status=initial_status,
            last_known_status=initial_status,
        )
        db.add(application)
        message = "Application registered"
    else:
        application.date_of_birth = date_of_birth.strip()
        application.email = email.strip().lower()
        application.phone = phone.strip()
        message = "Application updated"

    application.last_updated = utc_now()
    await db.commit()
    return redirect_to_dashboard(message)


@app.get("/admin")
async def admin_dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    query = select(Application).order_by(Application.last_updated.desc())
    applications = (await db.scalars(query)).all()

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "applications": applications,
            "statuses": STATUS_LIFECYCLE,
            "message": request.query_params.get("message"),
        },
    )


@app.post("/admin/update-status")
async def update_application_status(
    background_tasks: BackgroundTasks,
    file_no: str = Form(...),
    new_status: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if new_status not in STATUS_LIFECYCLE:
        raise HTTPException(status_code=400, detail="Invalid application status")

    application = await db.get(Application, file_no.strip().upper())
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    previous_status = application.current_status
    if previous_status == new_status:
        return redirect_to_admin("Status is already up to date")

    application.current_status = new_status
    application.last_known_status = new_status
    application.last_updated = utc_now()
    await db.commit()

    background_tasks.add_task(
        send_status_email,
        recipient=application.email,
        file_no=application.file_no,
        previous_status=previous_status,
        new_status=new_status,
    )
    return redirect_to_admin("Status updated and email queued")


async def run_status_check() -> None:
    """Send one email for each status change that has not been notified yet."""
    pending_emails: list[tuple[str, str, str, str]] = []

    async with AsyncSessionLocal() as db:
        applications = (await db.scalars(select(Application))).all()

        for application in applications:
            previous_status = application.last_known_status
            new_status = application.current_status

            if new_status == previous_status:
                continue

            application.last_known_status = new_status
            application.last_updated = utc_now()
            pending_emails.append(
                (application.email, application.file_no, previous_status, new_status)
            )

        await db.commit()

    await asyncio.gather(
        *(
            send_status_email(
                recipient=email,
                file_no=file_no,
                previous_status=previous_status,
                new_status=new_status,
            )
            for email, file_no, previous_status, new_status in pending_emails
        )
    )

    logger.info(
        "Status check completed: %d application(s), %d change(s)",
        len(applications),
        len(pending_emails),
    )


@app.post("/run-check")
async def trigger_status_check(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_status_check)
    return redirect_to_dashboard("Status check started")
