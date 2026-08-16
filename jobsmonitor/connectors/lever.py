import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class LeverConnector:
    """Generic connector for any company on Lever's public postings API.

    Docs: https://github.com/lever/postings-api
    Add a new Lever-hosted company by config alone — find their slug from
    jobs.lever.co/<slug>.

    Lever's `categories.location` is sometimes just the country ("Australia")
    rather than a city, and `categories.allLocations` may list several cities
    for one posting — we fold both into the location text we hand to the
    matcher so a Sydney mention anywhere is enough.
    """

    def __init__(self, company: str, slug: str):
        self.company = company
        self.slug = slug

    def fetch(self) -> list[Job]:
        url = f"https://api.lever.co/v0/postings/{self.slug}?mode=json"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: lever fetch failed: {e}") from e

        if not isinstance(data, list):
            raise ConnectorError(f"{self.company}: unexpected lever response shape (expected a list)")

        jobs = []
        for p in data:
            categories = p.get("categories") or {}
            locations = [categories.get("location", "")] + list(categories.get("allLocations") or [])
            location_text = "; ".join(loc for loc in locations if loc)

            jobs.append(
                Job(
                    company=self.company,
                    job_id=str(p["id"]),
                    title=p.get("text", ""),
                    url=p.get("hostedUrl", ""),
                    location=location_text,
                )
            )
        return jobs
