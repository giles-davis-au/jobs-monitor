from unittest.mock import MagicMock

from jobsmonitor.models import Job, LocationConfidence
from jobsmonitor.sheets import SheetConfig, SheetLogger, _escape


def make_logger():
    logger = SheetLogger.__new__(SheetLogger)  # bypass __init__ (no real gspread auth)
    logger.worksheet = MagicMock()
    return logger


def test_append_matches_builds_expected_rows():
    logger = make_logger()
    job = Job("Block", "1", "Program Manager", "https://block.xyz/careers/jobs/1", "Sydney, Australia")

    logger.append_matches([(job, LocationConfidence.CITY)], {"Block": "https://block.xyz"})

    logger.worksheet.append_rows.assert_called_once()
    rows, kwargs = logger.worksheet.append_rows.call_args
    row = rows[0][0]
    assert row[0] == "=ROW()-1"
    assert row[2] == '=HYPERLINK("https://block.xyz","Block")'
    assert row[3] == '=HYPERLINK("https://block.xyz/careers/jobs/1","Program Manager")'
    assert kwargs["value_input_option"] == "USER_ENTERED"


def test_append_matches_falls_back_to_plain_text_when_no_homepage():
    logger = make_logger()
    job = Job("Unknown Co", "1", "Role", "https://x/1", "Sydney")

    logger.append_matches([(job, LocationConfidence.CITY)], {})

    row = logger.worksheet.append_rows.call_args[0][0][0]
    assert row[2] == "Unknown Co"


def test_append_matches_noop_on_empty_list():
    logger = make_logger()
    logger.append_matches([], {})
    logger.worksheet.append_rows.assert_not_called()


def test_append_matches_writes_one_row_per_match_with_todays_date():
    logger = make_logger()
    job1 = Job("A", "1", "Role 1", "https://x/1", "Sydney")
    job2 = Job("B", "2", "Role 2", "https://x/2", "Sydney")

    logger.append_matches([(job1, LocationConfidence.CITY), (job2, LocationConfidence.CITY)], {})

    rows = logger.worksheet.append_rows.call_args[0][0]
    assert len(rows) == 2
    import re

    assert re.match(r"\d{2}/\d{2}/\d{4}", rows[0][1])


def test_escape_replaces_double_quotes_to_avoid_breaking_formula():
    assert _escape('Manager "Ops" Lead') == "Manager 'Ops' Lead"


def test_sheet_config_from_env_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEETS_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    assert SheetConfig.from_env() is None


def test_sheet_config_from_env_builds_config_when_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "/path/creds.json")
    monkeypatch.setenv("GOOGLE_SHEET_ID", "abc123")
    monkeypatch.setenv("GOOGLE_SHEET_GID", "999")

    config = SheetConfig.from_env()

    assert config.credentials_file == "/path/creds.json"
    assert config.sheet_id == "abc123"
    assert config.worksheet_gid == "999"
