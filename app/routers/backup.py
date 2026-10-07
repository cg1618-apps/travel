"""The 備份 button: back the database up to the owner's Google Sheet.

The router maps outcomes to status codes; the work is in
`app.services.sheet_backup.backup`. There is no restore route, deliberately:
restoring replaces every table, and when the app has died there is no page to
press anything on. It is `scripts/restore_sheet.py`.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.backup import BackupResponse
from app.services.sheet_backup.backup import BackupAlreadyRunning, NothingToBackUp, run_backup
from app.services.sheet_backup.client import (
    SheetClient,
    SheetsNotConfigured,
    SheetsUnavailable,
    open_spreadsheet,
)

router = APIRouter(prefix="/api/backup", tags=["Backup"])


def get_sheet_client() -> SheetClient:
    """The spreadsheet, opened. A dependency so the tests can hand in a fake."""
    try:
        return open_spreadsheet()
    except (SheetsNotConfigured, SheetsUnavailable) as error:
        raise HTTPException(status_code=503, detail=str(error)) from None


@router.post("", response_model=BackupResponse)
def backup(db: Session = Depends(get_db), client: SheetClient = Depends(get_sheet_client)):
    try:
        result = run_backup(db, client)
    except BackupAlreadyRunning as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except NothingToBackUp as error:
        # The wrong database, almost certainly. The sheet keeps the last backup.
        raise HTTPException(status_code=422, detail=str(error)) from None
    except SheetsUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    return BackupResponse(tabs=result.tabs, rows=result.rows, backed_up_at=result.backed_up_at)
