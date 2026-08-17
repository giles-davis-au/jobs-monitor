import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class BambooHrConnector:
    """Generic connector for companies on BambooHR's public careers API.

    `https://{company}.bamboohr.com/careers/list` is a public, unauthenticated
    JSON endpoint — no pagination needed, returns everything in one response.
    Find `bamboo_company` from a `{company}.bamboohr.com` link on the
    company's careers page.
    """

    def __init__(self, company: str, bamboo_company: str):
        self.company = company
        self.bamboo_company = bamboo_company

    def fetch(self) -> list[Job]:
        base = f"https://{self.bamboo_company}.bamboohr.com"
        try:
            with http_client() as client:
                resp = client.get(f"{base}/careers/list")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: bamboohr fetch failed: {e}") from e

        try:
            items = data["result"]
        except (KeyError, TypeError) as e:
            raise ConnectorError(f"{self.company}: unexpected bamboohr response shape: {e}") from e

        jobs = []
        for item in items:
            ats_location = item.get("atsLocation") or {}
            location = ", ".join(
                p for p in (ats_location.get("city"), ats_location.get("state"), ats_location.get("country")) if p
            )
            job_id = str(item.get("id", ""))

            jobs.append(
                Job(
                    company=self.company,
                    job_id=job_id,
                    title=item.get("jobOpeningName", ""),
                    url=f"{base}/careers/{job_id}",
                    location=location,
                )
            )
        return jobs
