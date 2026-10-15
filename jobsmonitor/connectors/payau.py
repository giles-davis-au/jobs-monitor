from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class PayAuConnector:
    """pay.com.au's careers page is a WordPress page whose roles sit inside
    `.jobs-listing-block`, rendered server-side — no ATS and no public API
    (WordPress REST exposes no jobs post type).

    Built while the page listed zero roles, so the markup of an actual role
    entry has never been seen. Rather than guess, this reads the links inside
    the listing block (any link is treated as a role) and fails loudly in
    two cases instead of silently reporting "no jobs":
      - the listing block is missing (page redesigned);
      - the block has content but no links (roles present in a form this
        parser doesn't understand).

    The page gives no location per role, so every role is reported as
    "Australia" — the matcher treats that as country-level and flags
    "verify city" rather than dropping it (deliberately over-catching).
    """

    def __init__(self, company: str = "pay.com.au", url: str = "https://pay.com.au/careers/"):
        self.company = company
        self.url = url

    def fetch(self) -> list[Job]:
        try:
            with http_client() as client:
                resp = client.get(self.url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: pay.com.au fetch failed: {e}") from e

        return self.parse_jobs(resp.text)

    def parse_jobs(self, html: str) -> list[Job]:
        block = BeautifulSoup(html, "html.parser").select_one(".jobs-listing-block")
        if block is None:
            raise ConnectorError(
                f"{self.company}: jobs listing block not found — page structure may have changed"
            )

        links = [a for a in block.select("a[href]") if a.get_text(strip=True)]
        if not links and block.get_text(strip=True):
            raise ConnectorError(
                f"{self.company}: listing block has content but no role links — "
                "page structure may have changed"
            )

        jobs = []
        for link in links:
            href = link["href"]
            jobs.append(
                Job(
                    company=self.company,
                    job_id=href,
                    title=link.get_text(" ", strip=True),
                    url=urljoin(self.url, href),
                    location="Australia",
                )
            )
        return jobs
