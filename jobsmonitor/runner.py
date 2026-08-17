import logging

from jobsmonitor.connectors.base import Connector, ConnectorError
from jobsmonitor.matcher import find_matches
from jobsmonitor.notifier import EmailConfig, send_degraded_alert, send_digest
from jobsmonitor.sheets import SheetLogger
from jobsmonitor.store import Store

logger = logging.getLogger("jobsmonitor")


def run(
    store: Store,
    connectors: list[Connector],
    keywords: list[str],
    email_config: EmailConfig,
    sheet_logger: SheetLogger | None = None,
    homepages: dict[str, str] | None = None,
) -> None:
    """One fetch-match-notify cycle across every configured company.

    Each company is independent: one connector failing never stops the rest
    from running, and never gets treated as "zero new jobs" — see
    docs/PLAN.md §6.
    """
    all_new_matches = []

    for connector in connectors:
        company = connector.company

        try:
            jobs = connector.fetch()
        except ConnectorError as e:
            logger.error("%s: connector error: %s", company, e)
            store.record_run(company, status="error", jobs_fetched=None, new_matches=0, error=str(e))
            send_degraded_alert(email_config, company, "error", str(e))
            continue

        jobs_fetched = len(jobs)
        last_ok = store.last_ok_jobs_fetched(company)

        if jobs_fetched == 0 and last_ok:
            error = f"returned 0 jobs this run; last successful run had {last_ok}"
            logger.warning("%s: %s", company, error)
            store.record_run(company, status="degraded", jobs_fetched=0, new_matches=0, error=error)
            send_degraded_alert(email_config, company, "degraded", error)
            continue

        matches = find_matches(jobs, keywords)
        new_matches = [(job, conf) for job, conf in matches if store.is_new(company, job.job_id)]
        for job, conf in new_matches:
            store.mark_seen(job, conf)

        store.record_run(company, status="ok", jobs_fetched=jobs_fetched, new_matches=len(new_matches))
        logger.info("%s: fetched=%d matches=%d new=%d", company, jobs_fetched, len(matches), len(new_matches))
        all_new_matches.extend(new_matches)

    if all_new_matches:
        send_digest(email_config, all_new_matches, keywords)

        if sheet_logger:
            try:
                sheet_logger.append_matches(all_new_matches, homepages or {})
            except Exception as e:
                # GSheet logging is a secondary channel — the email already
                # went out and the matches are already in seen_jobs, so a
                # failure here loses nothing, just logged rather than raised.
                logger.error("failed to append matches to Google Sheet: %s", e)

    logger.info(
        "run complete: %d new match(es) across %d companies", len(all_new_matches), len(connectors)
    )
