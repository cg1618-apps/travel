"""Every call this app makes to Google Sheets, and nothing about the data.

`SheetClient` wraps one gspread `Spreadsheet` and is the seam the tests use:
they hand it an in-memory `FakeSpreadsheet` instead, and an autouse guard in
`tests/conftest.py` makes building a real gspread client fail outright. The
backup and the restore never import gspread themselves.

Calls are batched - one values write and one clear for the whole backup rather
than two per tab, as media's `bulk_overwrite_sheet` does. Sheets allows sixty
writes a minute, and a backup with a dozen readable tabs at two calls each
would sit near that wall; a 429 waits a minute, which a request held open by
the tunnel cannot afford.

Values are written `RAW`, never `USER_ENTERED` - a deliberate divergence from
media. Under `USER_ENTERED` a booking code `0123` becomes the number 123 and
an ISO date becomes a date in the sheet's locale; under `RAW` a string stays
the string, so nothing needs escaping. The one exception is the 總覽 tab's
links, which are formulas by nature and written by `write_formulas`.
"""

import json
import logging
import re
import time
from collections.abc import Callable, Iterable
from typing import Any

import gspread
import requests
from google.auth.exceptions import GoogleAuthError
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, SpreadsheetNotFound
from gspread.utils import absolute_range_name, rowcol_to_a1

from app.config import settings

logger = logging.getLogger(__name__)

#: Sheets alone. Media also asks for `drive`, but `open_by_key` does not need
#: it, and the service account has only the Sheets API enabled.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Google answers with these when its own backend is momentarily unwell rather
# than when anything is wrong with the request, so they are safe to repeat.
TRANSIENT_STATUS_CODES = (500, 502, 503, 504)

#: The size a new tab is created at, grown on demand when a matrix is larger.
NEW_TAB_ROWS = 100
NEW_TAB_COLS = 26


class SheetsNotConfigured(RuntimeError):
    """GOOGLE_CREDENTIALS_JSON or GOOGLE_SHEET_ID is missing or unusable."""


class SheetsUnavailable(RuntimeError):
    """Google could not be reached, kept refusing, or refused us for good.

    Raised once retries are spent, and for the permanent refusals that mean
    the sheet is unreachable rather than the request wrong - a sheet not
    shared with the service account (403), a wrong id (404). Either way the
    caller's answer is the same: nothing was backed up, and why.
    """


# The two shapes gspread renders an API error in. Anchored, as in media: a bare
# three-digit number in a message must not be mistaken for a status.
_STATUS_IN_MESSAGE = (
    re.compile(r"\[(\d{3})\]"),
    re.compile(r"['\"]code['\"]\s*:\s*(\d{3})\b"),
)


def _status_code(error: Exception) -> int | None:
    """The HTTP status of a gspread APIError, wherever it survived.

    Media's helper, kept whole: the response first, then gspread 6's `.code`
    (which is -1 when the body could not be parsed, hence the `> 0`), then the
    message as the last resort.
    """
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int) and status > 0:
        return status

    code = getattr(error, "code", None)
    if isinstance(code, int) and code > 0:
        return code

    text = str(error)
    for pattern in _STATUS_IN_MESSAGE:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _execute_with_retry(func: Callable, *args, max_retries: int = 3, **kwargs) -> Any:
    """Call `func`, retrying what is worth retrying, as media does.

    A 429 means the per-minute quota is spent and waits most of a minute; a
    5xx or a dropped connection is a blip that usually clears in seconds.
    Once the retries are spent the error is `SheetsUnavailable`. A 403 or 404
    is permanent and becomes `SheetsUnavailable` at once; any other API error
    is a fault in the request and is raised as it is.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except APIError as error:
            status = _status_code(error)
            last_error = error
            if status == 429:
                wait = 60 * (attempt + 1)
                logger.warning("Sheets quota exceeded (429), attempt %s/%s; waiting %ss",
                               attempt + 1, max_retries, wait)
            elif status in TRANSIENT_STATUS_CODES:
                wait = 2 ** (attempt + 1)
                logger.warning("Sheets unavailable (%s), attempt %s/%s; retrying in %ss",
                               status, attempt + 1, max_retries, wait)
            elif status in (403, 404):
                raise SheetsUnavailable(
                    f"Google Sheets refused the request ({status}). Check that "
                    "GOOGLE_SHEET_ID is right and the sheet is shared with the "
                    "service account as an Editor."
                ) from error
            else:
                raise
        except requests.exceptions.RequestException as error:
            last_error = error
            wait = 2 ** (attempt + 1)
            logger.warning("Sheets unreachable, attempt %s/%s; retrying in %ss",
                           attempt + 1, max_retries, wait)
        except GoogleAuthError as error:
            # A revoked or malformed key does not get better by asking again.
            raise SheetsUnavailable(
                "Google refused the service account's credentials."
            ) from error
        # No point sleeping through the backoff of an attempt we will not make.
        if attempt < max_retries - 1:
            time.sleep(wait)

    logger.error("Sheets retries exhausted: %s", last_error)
    raise SheetsUnavailable(f"Google Sheets is unavailable: {last_error}")


def _authorize(info: dict) -> gspread.Client:
    """The one place a real gspread client is built. The tests' guard blocks it."""
    credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(credentials)


def open_spreadsheet(sheet_id: str | None = None) -> "SheetClient":
    """Open GOOGLE_SHEET_ID, or `sheet_id` when given, as the service account.

    Refuses with `SheetsNotConfigured` before touching the network when either
    setting is missing. The key's own error text is never passed on: a
    message about a malformed credential is the easiest place for a piece of
    it to leak into a log.
    """
    sheet_id = sheet_id or settings.google_sheet_id
    if not settings.google_credentials_json:
        raise SheetsNotConfigured("GOOGLE_CREDENTIALS_JSON is not set.")
    if not sheet_id:
        raise SheetsNotConfigured("GOOGLE_SHEET_ID is not set.")
    try:
        info = json.loads(settings.google_credentials_json)
        client = _authorize(info)
    except (ValueError, TypeError, KeyError):
        raise SheetsNotConfigured(
            "GOOGLE_CREDENTIALS_JSON is not a service-account key on one line."
        ) from None
    try:
        spreadsheet = _execute_with_retry(client.open_by_key, sheet_id)
    except SpreadsheetNotFound:
        raise SheetsUnavailable(
            "No spreadsheet with GOOGLE_SHEET_ID is shared with the service account."
        ) from None
    except PermissionError as error:
        # open_by_key turns a 403 into a BARE PermissionError, with the APIError
        # only as its cause, so the status-code handling above never sees it.
        # Google's reason is passed on: "the Sheets API is not enabled in the
        # key's project" and "not shared with the service account" need
        # different fixes, and neither message carries anything from the key.
        reason = f" Google says: {error.__cause__}" if error.__cause__ else ""
        raise SheetsUnavailable(
            "Google Sheets refused to open the sheet (403). Check that the Sheets "
            "API is enabled in the service account's project and that the sheet "
            f"is shared with the service account as an Editor.{reason}"
        ) from error
    return SheetClient(spreadsheet)


def _column(n: int) -> str:
    """1 -> A, 27 -> AA."""
    return rowcol_to_a1(1, n)[:-1]


class SheetClient:
    """The handful of operations the backup and restore need, each retried."""

    def __init__(self, spreadsheet):
        self.spreadsheet = spreadsheet

    def worksheets(self) -> dict[str, Any]:
        """Every tab, by title."""
        return {ws.title: ws for ws in _execute_with_retry(self.spreadsheet.worksheets)}

    def ensure_tabs(self, sizes: dict[str, tuple[int, int]]) -> dict[str, Any]:
        """Make each titled tab exist and be at least (rows, cols) large.

        A values write outside a tab's grid is refused by Sheets rather than
        growing it, so a tab is created or resized before it is written.
        """
        tabs = self.worksheets()
        for title, (rows, cols) in sizes.items():
            ws = tabs.get(title)
            if ws is None:
                tabs[title] = _execute_with_retry(
                    self.spreadsheet.add_worksheet,
                    title=title,
                    rows=max(rows, NEW_TAB_ROWS),
                    cols=max(cols, NEW_TAB_COLS),
                )
            elif ws.row_count < rows or ws.col_count < cols:
                _execute_with_retry(
                    ws.resize, rows=max(rows, ws.row_count), cols=max(cols, ws.col_count)
                )
        return tabs

    def overwrite(self, matrices: dict[str, list[list[Any]]]) -> None:
        """Replace each tab's contents with its matrix: write first, trim after.

        The new values go in with one `RAW` write from A1, and only then is
        whatever lies beyond them cleared, so a failed write leaves the
        previous backup in place rather than an empty tab.

        A header-only matrix is written like any other, trimming the rows the
        tab held: a table that has reached zero rows is a fact to back up.
        Media also refuses to blank a tab that holds data; here that would make
        every later backup refuse once the last route or label option was
        deleted, and the hazard it guards against - an empty worktree database
        - is the backup's all-empty refusal instead.
        """
        sizes = {
            title: (len(matrix), max((len(row) for row in matrix), default=1))
            for title, matrix in matrices.items()
        }
        # Every row padded to the matrix's width: a short row, or a blank one,
        # would otherwise leave last backup's cells standing beside it - the
        # trim below only reaches what lies outside the new matrix.
        matrices = {
            title: [list(row) + [""] * (sizes[title][1] - len(row)) for row in matrix]
            for title, matrix in matrices.items()
        }
        tabs = self.ensure_tabs(sizes)
        _execute_with_retry(
            self.spreadsheet.values_batch_update,
            {
                "valueInputOption": "RAW",
                "data": [
                    {"range": absolute_range_name(title, "A1"), "values": matrix}
                    for title, matrix in matrices.items()
                    if matrix
                ],
            },
        )

        leftovers = []
        for title, (rows, cols) in sizes.items():
            ws = tabs[title]
            if ws.row_count > rows:
                leftovers.append(absolute_range_name(
                    title, f"A{rows + 1}:{_column(ws.col_count)}{ws.row_count}"
                ))
            if ws.col_count > cols and rows:
                leftovers.append(absolute_range_name(
                    title, f"{_column(cols + 1)}1:{_column(ws.col_count)}{rows}"
                ))
        if leftovers:
            _execute_with_retry(self.spreadsheet.values_batch_clear, body={"ranges": leftovers})

    def write_formulas(self, title: str, cells: dict[str, str]) -> None:
        """Write formulas (`=HYPERLINK(...)`) to single cells, `USER_ENTERED`.

        The only `USER_ENTERED` write there is: a link is a formula, and under
        `RAW` it would be stored as its own source text.
        """
        if not cells:
            return
        _execute_with_retry(
            self.spreadsheet.values_batch_update,
            {
                "valueInputOption": "USER_ENTERED",
                "data": [
                    {"range": absolute_range_name(title, cell), "values": [[formula]]}
                    for cell, formula in cells.items()
                ],
            },
        )

    def delete_tabs(self, titles: Iterable[str]) -> None:
        tabs = self.worksheets()
        for title in titles:
            _execute_with_retry(self.spreadsheet.del_worksheet, tabs[title])

    def reorder(self, titles: list[str]) -> None:
        """Put `titles` first, in this order. Every other tab follows them."""
        tabs = self.worksheets()
        _execute_with_retry(self.spreadsheet.reorder_worksheets, [tabs[t] for t in titles])

    def read(self, titles: list[str]) -> dict[str, list[list[str]]]:
        """Every value in each tab, as text, rows padded to the widest one.

        The API drops trailing empty cells from each row, so a row whose last
        columns are null comes back short; padding is what keeps a value under
        its header.
        """
        response = _execute_with_retry(
            self.spreadsheet.values_batch_get,
            [absolute_range_name(title) for title in titles],
        )
        result = {}
        for title, value_range in zip(titles, response.get("valueRanges", []), strict=True):
            rows = [[str(cell) for cell in row] for row in value_range.get("values", [])]
            width = max((len(row) for row in rows), default=0)
            result[title] = [row + [""] * (width - len(row)) for row in rows]
        return result
