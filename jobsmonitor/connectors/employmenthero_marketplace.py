import json

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class EmploymentHeroMarketplaceConnector:
    """For companies whose jobs live on employmenthero.com's own jobs
    marketplace (linked out from their careers page, e.g. Smokeball) rather
    than embedded via the ats-cdn widget on their own domain (see
    `employmenthero.py` for that variant).

    The org's job list is embedded directly as JSON in a WordPress
    Interactivity API `data-wp-context` attribute on the page — no separate
    API call needed. Find `org_slug` from the "sameAs" field in a job's
    JSON-LD structured data on an employmenthero.com job posting page, e.g.
    `.../jobs/organisations/smokeball-australia-8gtiq/` -> org_slug
    `smokeball-australia-8gtiq`.
    """

    def __init__(self, company: str, org_slug: str):
        self.company = company
        self.org_slug = org_slug

    def fetch(self) -> list[Job]:
        url = f"https://employmenthero.com/jobs/organisations/{self.org_slug}/"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: employment hero marketplace fetch failed: {e}") from e

        container = soup.select_one("div.company-jobs-list--jobs-list-container")
        if container is None or not container.has_attr("data-wp-context"):
            raise ConnectorError(
                f"{self.company}: jobs-list container not found — page structure may have changed"
            )

        try:
            items = json.loads(container["data-wp-context"])["items"]
        except (ValueError, KeyError) as e:
            raise ConnectorError(f"{self.company}: unexpected jobs-list data shape: {e}") from e

        return [
            Job(
                company=self.company,
                job_id=item["id"],
                title=item.get("title", ""),
                url=item.get("jobUrl", ""),
                location=item.get("vendor_location_name", ""),
            )
            for item in items
        ]
