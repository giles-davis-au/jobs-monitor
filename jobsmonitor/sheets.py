import os
from dataclasses import dataclass
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from jobsmonitor.models import Job, LocationConfidence

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@dataclass
class SheetConfig:
    credentials_file: str
    sheet_id: str
    worksheet_gid: str | None = None

    @classmethod
    def from_env(cls) -> "SheetConfig | None":
        """None (feature disabled) unless both required env vars are set —
        this makes GSheet logging opt-in, so the tool keeps working before
        the one-time Google Cloud service-account setup is done.
        """
        credentials_file = os.environ.get("GOOGLE_SHEETS_CREDENTIALS_FILE")
        sheet_id = os.environ.get("GOOGLE_SHEET_ID")
        if not credentials_file or not sheet_id:
            return None
        return cls(
            credentials_file=credentials_file,
            sheet_id=sheet_id,
            worksheet_gid=os.environ.get("GOOGLE_SHEET_GID"),
        )


class SheetLogger:
    """Appends new job matches to a Google Sheet via a service account.

    Assumes the target sheet already has a header row (# | Date Retrieved |
    Company | Job Title) — this class only ever appends after the last
    existing row, never touches row 1, so it won't clobber a sheet the user
    has already set up.

    The "#" column is written as the formula `=ROW()-1` rather than a
    literal number, so it stays correct even if rows are later
    deleted/reordered by hand (self-numbering, no need to read current sheet
    state first to compute the next number).
    """

    def __init__(self, config: SheetConfig):
        creds = Credentials.from_service_account_file(config.credentials_file, scopes=SCOPES)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(config.sheet_id)
        if config.worksheet_gid:
            self.worksheet = spreadsheet.get_worksheet_by_id(int(config.worksheet_gid))
        else:
            self.worksheet = spreadsheet.sheet1

    def append_matches(
        self, matches: list[tuple[Job, LocationConfidence]], homepages: dict[str, str]
    ) -> None:
        if not matches:
            return

        today = datetime.now().strftime("%d/%m/%Y")
        rows = []
        for job, _confidence in matches:
            homepage = homepages.get(job.company)
            company_cell = (
                f'=HYPERLINK("{homepage}","{_escape(job.company)}")'
                if homepage
                else job.company
            )
            title_cell = f'=HYPERLINK("{job.url}","{_escape(job.title)}")'
            rows.append(["=ROW()-1", today, company_cell, title_cell])

        self.worksheet.append_rows(rows, value_input_option="USER_ENTERED")


def _escape(text: str) -> str:
    # HYPERLINK's second argument is a quoted string literal inside the
    # formula — a literal double-quote in a job title would otherwise break it.
    return text.replace('"', "'")
