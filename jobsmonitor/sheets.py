import os
from dataclasses import dataclass
from datetime import datetime

import httpx

from jobsmonitor.models import Job, LocationConfidence


@dataclass
class SheetConfig:
    webhook_url: str
    secret: str

    @classmethod
    def from_env(cls) -> "SheetConfig | None":
        """None (feature disabled) unless both env vars are set — this makes
        GSheet logging opt-in, so the tool keeps working before the Apps
        Script webhook is deployed.
        """
        webhook_url = os.environ.get("GOOGLE_SHEETS_WEBHOOK_URL")
        secret = os.environ.get("GOOGLE_SHEETS_WEBHOOK_SECRET")
        if not webhook_url or not secret:
            return None
        return cls(webhook_url=webhook_url, secret=secret)


class SheetLogger:
    """Appends new job matches to a Google Sheet via a small Apps Script Web
    App bound directly to the sheet — no Google Cloud project, no service
    account, no credential file to protect. See README for the Apps Script
    source and one-time deployment steps.

    The webhook URL plus a shared secret (checked inside the Apps Script,
    not by Google) is the whole auth story — equivalent security posture to
    any other bearer-token webhook, e.g. the Resend API key.
    """

    def __init__(self, config: SheetConfig):
        self.config = config

    def append_matches(
        self, matches: list[tuple[Job, LocationConfidence]], homepages: dict[str, str]
    ) -> None:
        if not matches:
            return

        # Deliberately local (not UTC): the script runs on the user's own
        # Mac, and "Date Retrieved" should read as their own local date.
        today = datetime.now().strftime("%d/%m/%Y")  # noqa: DTZ005
        rows = [
            {
                "dateRetrieved": today,
                "companyName": job.company,
                "companyUrl": homepages.get(job.company, ""),
                "jobTitle": job.title,
                "jobUrl": job.url,
            }
            for job, _confidence in matches
        ]

        resp = httpx.post(
            self.config.webhook_url,
            json={"secret": self.config.secret, "rows": rows},
            timeout=20,
            # Apps Script Web App URLs (.../exec) respond via a 302 to
            # script.googleusercontent.com to actually deliver the content —
            # this is normal, not an error condition, so follow it.
            follow_redirects=True,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "ok":
            raise RuntimeError(f"Apps Script webhook returned unexpected response: {body}")
