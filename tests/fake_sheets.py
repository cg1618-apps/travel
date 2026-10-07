"""An in-memory Google spreadsheet: the handful of calls `SheetClient` makes.

What it imitates on purpose, because the code under test depends on each:

- a write outside a tab's grid is refused, as Sheets refuses it, so a tab that
  was not grown first fails here too;
- a `RAW` write stores the text it was given, and a bool as TRUE/FALSE;
- a read drops each row's trailing empty cells and the trailing empty rows,
  and omits `values` for an empty range - the shapes the real API answers in.

`calls` records every call by name, so a test can say what was NOT done.
"""

import re

from gspread.exceptions import APIError

_RANGE = re.compile(r"^'((?:[^']|'')*)'(?:!(.*))?$")
_CELL = re.compile(r"^([A-Z]+)(\d+)$")
_ROWS = re.compile(r"^(\d+):(\d+)$")


def _col_number(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


class FakeResponse:
    """Enough of a `requests.Response` for gspread's APIError to read."""

    def __init__(self, status: int):
        self.status_code = status
        self.text = f"status {status}"

    def json(self):
        return {"error": {"code": self.status_code, "message": self.text, "status": "FAKE"}}


def api_error(status: int) -> APIError:
    return APIError(FakeResponse(status))


class FakeWorksheet:
    def __init__(self, sheet_id: int, title: str, rows: int = 100, cols: int = 26):
        self.id = sheet_id
        self.title = title
        self.row_count = rows
        self.col_count = cols
        self.cells: dict[tuple[int, int], str] = {}  # (row, col), both 1-based

    def resize(self, rows=None, cols=None):
        self.row_count = rows or self.row_count
        self.col_count = cols or self.col_count

    def values(self) -> list[list[str]]:
        """Every value, as the API would answer a read of the whole tab."""
        if not self.cells:
            return []
        rows = max(r for r, _ in self.cells)
        out = []
        for r in range(1, rows + 1):
            cols = [c for (rr, c), v in self.cells.items() if rr == r and v != ""]
            width = max(cols, default=0)
            out.append([self.cells.get((r, c), "") for c in range(1, width + 1)])
        while out and not out[-1]:
            out.pop()
        return out

    def set_rows(self, matrix: list[list[str]]) -> None:
        """Test setup: replace the tab's contents."""
        self.cells = {
            (r, c): str(v) for r, row in enumerate(matrix, 1) for c, v in enumerate(row, 1) if v != ""
        }


class FakeSpreadsheet:
    def __init__(self):
        self.tabs: list[FakeWorksheet] = []
        self.next_id = 1000
        self.calls: list[str] = []
        #: method name -> exception raised on every call to it.
        self.failures: dict[str, Exception] = {}

    # --- test helpers -------------------------------------------------------

    def tab(self, title: str) -> FakeWorksheet:
        return next(ws for ws in self.tabs if ws.title == title)

    def titles(self) -> list[str]:
        return [ws.title for ws in self.tabs]

    def add_tab(self, title: str, matrix: list[list[str]] = ()) -> FakeWorksheet:
        ws = self.add_worksheet(title=title, rows=100, cols=26)
        ws.set_rows(list(matrix))
        self.calls.clear()
        return ws

    # --- the gspread surface ------------------------------------------------

    def _record(self, name: str) -> None:
        self.calls.append(name)
        if name in self.failures:
            raise self.failures[name]

    def worksheets(self):
        self._record("worksheets")
        return list(self.tabs)

    def add_worksheet(self, title, rows, cols, index=None):
        self._record("add_worksheet")
        if any(ws.title.casefold() == title.casefold() for ws in self.tabs):
            raise api_error(400)
        self.next_id += 1
        ws = FakeWorksheet(self.next_id, title, rows, cols)
        self.tabs.append(ws)
        return ws

    def del_worksheet(self, worksheet):
        self._record("del_worksheet")
        self.tabs.remove(worksheet)

    def reorder_worksheets(self, worksheets_in_desired_order):
        """gspread's rule: the named tabs first, every other one after them."""
        self._record("reorder_worksheets")
        first = list(worksheets_in_desired_order)
        self.tabs = first + [ws for ws in self.tabs if ws not in first]

    def _resolve(self, a1: str):
        match = _RANGE.match(a1)
        assert match, f"unquoted range {a1!r}"
        title = match.group(1).replace("''", "'")
        ws = next((w for w in self.tabs if w.title == title), None)
        if ws is None:
            raise api_error(400)
        return ws, match.group(2)

    def values_batch_update(self, body=None):
        self._record("values_batch_update")
        raw = body["valueInputOption"] == "RAW"
        for entry in body["data"]:
            ws, cell = self._resolve(entry["range"])
            col_letters, row = _CELL.match(cell).groups()
            top, left = int(row), _col_number(col_letters)
            for r, values in enumerate(entry["values"], top):
                for c, value in enumerate(values, left):
                    if r > ws.row_count or c > ws.col_count:
                        raise api_error(400)  # "exceeds grid limits"
                    if raw and isinstance(value, bool):
                        value = "TRUE" if value else "FALSE"
                    ws.cells[(r, c)] = str(value)

    def values_batch_clear(self, params=None, body=None):
        self._record("values_batch_clear")
        for a1 in body["ranges"]:
            ws, span = self._resolve(a1)
            start, end = span.split(":")
            c1, r1 = _CELL.match(start).groups()
            c2, r2 = _CELL.match(end).groups()
            for key in list(ws.cells):
                r, c = key
                if int(r1) <= r <= int(r2) and _col_number(c1) <= c <= _col_number(c2):
                    del ws.cells[key]

    def values_batch_get(self, ranges, params=None):
        self._record("values_batch_get")
        out = []
        for a1 in ranges:
            ws, span = self._resolve(a1)
            values = ws.values()
            if span:
                first, last = map(int, _ROWS.match(span).groups())
                values = values[first - 1:last]
            out.append({"range": a1, "values": values} if values else {"range": a1})
        return {"valueRanges": out}
