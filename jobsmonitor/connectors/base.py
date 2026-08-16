from typing import Protocol

import httpx

from jobsmonitor.models import Job

DEFAULT_TIMEOUT = 15.0
USER_AGENT = "jobs-monitor/0.1 (personal use; contact: gilesbdavis@gmail.com)"


class ConnectorError(Exception):
    """A connector could not produce a job list: network failure, non-2xx
    response, or a response shape that doesn't match what we expect.

    Deliberately broad — the runner treats any ConnectorError as a failed run
    (status='error') rather than silently reporting zero jobs. See docs/PLAN.md §6.
    """


class Connector(Protocol):
    company: str

    def fetch(self) -> list[Job]:
        """Return every currently-open job the source lists, unfiltered.

        Raises ConnectorError on any failure — never returns an empty list to
        mean "something went wrong" (empty list must only ever mean "the
        source genuinely has zero open roles right now").
        """
        ...


def http_client() -> httpx.Client:
    return httpx.Client(
        timeout=DEFAULT_TIMEOUT,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    )
