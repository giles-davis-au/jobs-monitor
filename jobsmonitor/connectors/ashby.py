import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class AshbyConnector:
    """Generic connector for any company on Ashby's public job board API.

    Docs: https://developers.ashbyhq.com/reference/jobboardsync
    Add a new Ashby-hosted company by config alone — find their board name
    from jobs.ashbyhq.com/<board>.
    """

    def __init__(self, company: str, board: str):
        self.company = company
        self.board = board

    def fetch(self) -> list[Job]:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.board}"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: ashby fetch failed: {e}") from e

        jobs = data.get("jobs")
        if jobs is None:
            raise ConnectorError(f"{self.company}: unexpected ashby response shape (no 'jobs' key)")

        result = []
        for j in jobs:
            secondary = [sl.get("location", "") for sl in (j.get("secondaryLocations") or [])]
            locations = [j.get("location", "")] + secondary
            location_text = "; ".join(loc for loc in locations if loc)

            result.append(
                Job(
                    company=self.company,
                    job_id=str(j["id"]),
                    title=j.get("title", ""),
                    url=j.get("jobUrl", ""),
                    location=location_text,
                )
            )
        return result
