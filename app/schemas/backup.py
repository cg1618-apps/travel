from datetime import datetime

from pydantic import BaseModel


class BackupResponse(BaseModel):
    """What a finished backup wrote: tabs written, rows per table, and when."""

    tabs: int
    rows: dict[str, int]
    backed_up_at: datetime
