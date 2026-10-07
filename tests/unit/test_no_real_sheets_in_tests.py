"""The suite may never reach the real Google Sheet.

The autouse `_no_real_google_sheets` guard in tests/conftest.py is what stops
it, and this file is what proves the guard is armed. Without these, deleting
the fixture would break nothing visible, and the first test to forget the
fake would back the test database up over the owner's sheet.
"""

import gspread
import pytest

from app.services.sheet_backup import client as sheet_client


def test_building_a_gspread_client_is_an_error():
    with pytest.raises(AssertionError, match="real gspread client"):
        gspread.Client(auth=None)


def test_the_apps_own_path_to_google_is_blocked_too(monkeypatch):
    """Configured as on a developer's machine, `open_spreadsheet` still stops.

    The key is a dummy and its parsing is stubbed, so this reaches exactly the
    point where a real client would be built - and the guard fires there.
    """
    monkeypatch.setattr(sheet_client.settings, "google_credentials_json", '{"type": "dummy"}')
    monkeypatch.setattr(sheet_client.settings, "google_sheet_id", "dummy-sheet")
    monkeypatch.setattr(
        sheet_client.Credentials, "from_service_account_info", lambda info, scopes: object()
    )
    with pytest.raises(AssertionError, match="real gspread client"):
        sheet_client.open_spreadsheet()


def test_a_fake_spreadsheet_is_still_usable():
    """The guard must not get in the way of the normal pattern."""
    from tests.fake_sheets import FakeSpreadsheet

    client = sheet_client.SheetClient(FakeSpreadsheet())
    client.overwrite({"Tab": [["a"], ["1"]]})
    assert client.read(["Tab"]) == {"Tab": [["a"], ["1"]]}
