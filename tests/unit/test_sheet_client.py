"""SheetClient against the fake: write first, trim after, retry, refuse clearly."""

import pytest

from app.services.sheet_backup import client as sheet_client
from app.services.sheet_backup.client import (
    SheetClient,
    SheetsNotConfigured,
    SheetsUnavailable,
)
from app.services.sheet_backup.readable import MAX_TITLE, tab_titles
from tests.fake_sheets import FakeResponse, FakeSpreadsheet, api_error


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(sheet_client.time, "sleep", lambda seconds: None)


@pytest.fixture
def fake():
    return FakeSpreadsheet()


def test_new_data_is_written_before_the_leftovers_are_cleared(fake):
    fake.add_tab("Trip", [["id", "name", "notes"], ["1", "a", "x"], ["2", "b", "y"], ["3", "c", "z"]])
    SheetClient(fake).overwrite({"Trip": [["id", "name"], ["1", "a"]]})
    assert fake.calls.index("values_batch_update") < fake.calls.index("values_batch_clear")
    assert fake.tab("Trip").values() == [["id", "name"], ["1", "a"]]


def test_a_failed_write_leaves_the_previous_backup_and_clears_nothing(fake):
    fake.add_tab("Trip", [["id"], ["1"], ["2"]])
    fake.failures["values_batch_update"] = api_error(400)
    with pytest.raises(sheet_client.APIError):
        SheetClient(fake).overwrite({"Trip": [["id"], ["9"]]})
    assert "values_batch_clear" not in fake.calls
    assert fake.tab("Trip").values() == [["id"], ["1"], ["2"]]


def test_a_blank_row_in_the_matrix_clears_what_stood_there(fake):
    fake.add_tab("清單 · a", [["a"], ["old", "old", "old"]])
    SheetClient(fake).overwrite({"清單 · a": [["a", "b"], [], ["c"]]})
    assert fake.tab("清單 · a").values() == [["a", "b"], [], ["c"]]


def test_a_header_only_write_trims_the_rows_a_tab_held(fake):
    # Load-bearing: the tab holds data rows, so "header-only" has something
    # to trim. A table at zero rows is backed up as exactly that.
    fake.add_tab("Trip", [["id", "name"], ["1", "a"], ["2", "b"]])
    SheetClient(fake).overwrite({"Trip": [["id", "name"]]})
    assert fake.tab("Trip").values() == [["id", "name"]]


def test_a_tab_too_small_for_its_matrix_is_grown_first(fake):
    fake.add_tab("Trip").resize(rows=2, cols=2)
    matrix = [["id", "a", "b"], *([str(n), "", ""] for n in range(1, 6))]
    SheetClient(fake).overwrite({"Trip": matrix})
    assert fake.tab("Trip").values()[-1] == ["5"]


def test_a_5xx_is_retried_and_then_is_unavailable(fake):
    fake.failures["worksheets"] = api_error(503)
    with pytest.raises(SheetsUnavailable):
        SheetClient(fake).worksheets()
    assert fake.calls.count("worksheets") == 3


def test_a_429_is_retried_until_it_clears(fake, monkeypatch):
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise api_error(429)
        return "ok"

    assert sheet_client._execute_with_retry(flaky) == "ok"
    assert len(attempts) == 3


def test_a_403_is_unavailable_at_once_naming_the_share(fake):
    fake.failures["worksheets"] = api_error(403)
    with pytest.raises(SheetsUnavailable, match="shared with the service account"):
        SheetClient(fake).worksheets()
    assert fake.calls.count("worksheets") == 1


def test_a_400_is_a_fault_in_the_request_and_raised_as_it_is(fake):
    fake.failures["worksheets"] = api_error(400)
    with pytest.raises(sheet_client.APIError):
        SheetClient(fake).worksheets()


@pytest.mark.parametrize(("setting", "message"), [
    ("google_credentials_json", "GOOGLE_CREDENTIALS_JSON"),
    ("google_sheet_id", "GOOGLE_SHEET_ID"),
])
def test_a_missing_setting_is_named(monkeypatch, setting, message):
    monkeypatch.setattr(sheet_client.settings, "google_credentials_json", '{"type": "x"}')
    monkeypatch.setattr(sheet_client.settings, "google_sheet_id", "sheet")
    monkeypatch.setattr(sheet_client.settings, setting, None)
    with pytest.raises(SheetsNotConfigured, match=message):
        sheet_client.open_spreadsheet()


class _RefusingClient:
    """What `_authorize` returns when Google refuses to open the sheet."""

    def __init__(self, error: Exception):
        self.error = error

    def open_by_key(self, key):
        raise self.error


def _configured(monkeypatch, client):
    monkeypatch.setattr(sheet_client.settings, "google_credentials_json", '{"type": "x"}')
    monkeypatch.setattr(sheet_client.settings, "google_sheet_id", "sheet")
    monkeypatch.setattr(sheet_client, "_authorize", lambda info: client)


def test_a_403_while_opening_is_unavailable_and_says_why(monkeypatch):
    """gspread's open_by_key turns a 403 into a BARE PermissionError, not an
    APIError, so nothing that reads a status code sees it. Found by the first
    real run: the Sheets API was not yet enabled in the key's project, and the
    command died with a traceback (the route would have answered 500).
    Google's reason is kept - "API disabled" and "not shared" need different
    fixes, and neither message carries anything from the key."""
    response = FakeResponse(403)
    response.text = "Google Sheets API has not been used in project 1 before"
    cause = sheet_client.APIError(response)
    error = PermissionError()
    error.__cause__ = cause
    _configured(monkeypatch, _RefusingClient(error))
    with pytest.raises(SheetsUnavailable, match="has not been used in project 1"):
        sheet_client.open_spreadsheet()


def test_a_sheet_that_does_not_exist_is_unavailable_naming_the_share(monkeypatch):
    _configured(monkeypatch, _RefusingClient(sheet_client.SpreadsheetNotFound()))
    with pytest.raises(SheetsUnavailable, match="shared with the service account"):
        sheet_client.open_spreadsheet()


def test_a_key_that_is_not_json_is_refused_without_quoting_it(monkeypatch):
    monkeypatch.setattr(sheet_client.settings, "google_credentials_json", "not-json-SECRETISH")
    monkeypatch.setattr(sheet_client.settings, "google_sheet_id", "sheet")
    with pytest.raises(SheetsNotConfigured) as refused:
        sheet_client.open_spreadsheet()
    assert "SECRETISH" not in str(refused.value)


class Named:
    def __init__(self, id, name):
        self.id, self.name = id, name


def test_tab_names_are_capped_and_duplicates_numbered_in_id_order():
    long = "x" * 200
    titles = tab_titles("清單 · ", [Named(3, "彰化"), Named(1, "彰化"), Named(2, long), Named(4, long)])
    assert titles[1] == "清單 · 彰化"
    assert titles[3] == "清單 · 彰化 (2)"
    assert len(titles[2]) == MAX_TITLE
    assert len(titles[4]) == MAX_TITLE and titles[4].endswith(" (2)")
