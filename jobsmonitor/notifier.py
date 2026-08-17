import os
from dataclasses import dataclass

import httpx

from jobsmonitor.models import Job, LocationConfidence

RESEND_API_URL = "https://api.resend.com/emails"


@dataclass
class EmailConfig:
    api_key: str
    from_addr: str
    to_addr: str

    @classmethod
    def from_env(cls) -> "EmailConfig":
        try:
            return cls(
                api_key=os.environ["RESEND_API_KEY"],
                # Resend's shared sandbox sender — works with no domain setup,
                # but can only send to the account's own verified address,
                # which is exactly our personal-tool use case. Override via
                # RESEND_FROM once/if a custom domain is verified.
                from_addr=os.environ.get("RESEND_FROM", "onboarding@resend.dev"),
                to_addr=os.environ["NOTIFY_EMAIL_TO"],
            )
        except KeyError as e:
            raise RuntimeError(
                f"Missing required env var {e} — copy .env.example to .env and fill it in"
            ) from e


def _send(config: EmailConfig, subject: str, body: str) -> None:
    resp = httpx.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {config.api_key}"},
        json={
            "from": config.from_addr,
            "to": [config.to_addr],
            "subject": subject,
            "text": body,
        },
        timeout=20,
    )
    resp.raise_for_status()


def send_digest(
    config: EmailConfig, matches: list[tuple[Job, LocationConfidence]], keywords: list[str]
) -> None:
    """Sent every run, match or no match — this is deliberately also a
    heartbeat: getting nothing at all (rather than a "0 new matches" email)
    after a scheduled run is the signal that something upstream (Resend,
    the whole run, etc.) may be silently broken, not just that there was
    nothing to report.
    """
    lines = ["Searching for: " + ", ".join(keywords), ""]

    if matches:
        lines.append(f"{len(matches)} new Sydney job match(es):")
        lines.append("")
        for job, confidence in matches:
            flag = (
                "  [location: country-only — verify city]"
                if confidence == LocationConfidence.COUNTRY_ONLY
                else ""
            )
            lines.append(f"- {job.title} ({job.company}){flag}")
            lines.append(f"  {job.location}")
            lines.append(f"  {job.url}")
            lines.append("")
        subject = f"[jobs-monitor] {len(matches)} new match(es)"
    else:
        lines.append("No new matches this run.")
        subject = "[jobs-monitor] 0 new matches"

    _send(config, subject, "\n".join(lines))


def send_degraded_alert(config: EmailConfig, company: str, status: str, error: str | None) -> None:
    """Sent whenever a connector fails or looks broken — always sent, even if
    it means an otherwise-empty run, so a broken scraper is never silently
    indistinguishable from "no new jobs" (see docs/PLAN.md §6).
    """
    subject = f"[jobs-monitor] ALERT: {company} connector {status}"
    body = (
        f"The {company} connector reported status={status}.\n\n"
        f"Error: {error or '(no error message — see run history for details)'}\n\n"
        "This usually means the site's page structure changed, or it's "
        "temporarily unreachable. Check `python run.py --status` for history."
    )
    _send(config, subject, body)
