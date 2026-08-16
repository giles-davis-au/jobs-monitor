import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from jobsmonitor.models import Job, LocationConfidence


@dataclass
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    to_addr: str

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        try:
            return cls(
                host=os.environ["SMTP_HOST"],
                port=int(os.environ.get("SMTP_PORT", "587")),
                username=os.environ["SMTP_USERNAME"],
                password=os.environ["SMTP_PASSWORD"],
                to_addr=os.environ.get("NOTIFY_EMAIL_TO", os.environ["SMTP_USERNAME"]),
            )
        except KeyError as e:
            raise RuntimeError(
                f"Missing required env var {e} — copy .env.example to .env and fill it in"
            ) from e


def _send(config: SmtpConfig, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.username
    msg["To"] = config.to_addr
    msg.set_content(body)

    with smtplib.SMTP(config.host, config.port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(config.username, config.password)
        smtp.send_message(msg)


def send_digest(config: SmtpConfig, matches: list[tuple[Job, LocationConfidence]]) -> None:
    """The normal-case email: only sent when there's something to report."""
    if not matches:
        return

    lines = [f"{len(matches)} new Sydney job match(es):", ""]
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
    _send(config, subject, "\n".join(lines))


def send_degraded_alert(config: SmtpConfig, company: str, status: str, error: str | None) -> None:
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
