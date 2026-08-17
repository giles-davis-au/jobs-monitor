import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class BreezyConnector:
    """Generic connector for companies on Breezy HR's public job board API.

    `https://{company}.breezy.hr/json` is Breezy's own public, unauthenticated
    listing endpoint — no pagination needed, it returns everything in one
    response. Find `company` from a `{company}.breezy.hr` link on the
    company's careers page (for Stake, buried among many Next.js data-
    prefetch requests, not obvious from the visible page content).
    """

    def __init__(self, company: str, breezy_company: str):
        self.company = company
        self.breezy_company = breezy_company

    def fetch(self) -> list[Job]:
        url = f"https://{self.breezy_company}.breezy.hr/json"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: breezy fetch failed: {e}") from e

        if not isinstance(data, list):
            raise ConnectorError(f"{self.company}: unexpected breezy response shape (expected a list)")

        jobs = []
        for j in data:
            location = j.get("location") or {}
            parts = [
                location.get("city"),
                (location.get("state") or {}).get("name"),
                (location.get("country") or {}).get("name"),
            ]
            location_text = ", ".join(p for p in parts if p)

            jobs.append(
                Job(
                    company=self.company,
                    job_id=str(j.get("id", "")),
                    title=j.get("name", ""),
                    url=j.get("url", ""),
                    location=location_text,
                )
            )
        return jobs
