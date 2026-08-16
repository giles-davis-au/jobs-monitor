import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class WorkableConnector:
    """Generic connector for any company on Workable's public embed-widget API.

    The account id is numeric and appears in the site's embed snippet, e.g.
    `whr_embed(157387, {...})` — it's the same regardless of the widget's own
    display config (Rokt's widget only *shows* country, but the underlying
    API still returns full city/state/country per job).
    """

    def __init__(self, company: str, account_id: str):
        self.company = company
        self.account_id = account_id

    def fetch(self) -> list[Job]:
        url = f"https://apply.workable.com/api/v1/widget/accounts/{self.account_id}"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: workable fetch failed: {e}") from e

        jobs = data.get("jobs")
        if jobs is None:
            raise ConnectorError(f"{self.company}: unexpected workable response shape (no 'jobs' key)")

        result = []
        for j in jobs:
            location_parts = [j.get("city", ""), j.get("state", ""), j.get("country", "")]
            location_text = ", ".join(p for p in location_parts if p)

            result.append(
                Job(
                    company=self.company,
                    job_id=j.get("shortcode", j.get("url", "")),
                    title=j.get("title", ""),
                    url=j.get("url", ""),
                    location=location_text,
                )
            )
        return result
