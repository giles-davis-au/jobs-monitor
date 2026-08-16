import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class GreenhouseConnector:
    """Generic connector for any company on Greenhouse's public job board API.

    Docs: https://developers.greenhouse.io/job-board.html
    Add a new Greenhouse-hosted company by config alone — find their board
    token from the board URL (boards.greenhouse.io/<token>) or by watching
    network requests on their careers page for boards-api.greenhouse.io.
    """

    def __init__(self, company: str, board_token: str):
        self.company = company
        self.board_token = board_token

    def fetch(self) -> list[Job]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs?content=false"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: greenhouse fetch failed: {e}") from e

        jobs = data.get("jobs")
        if jobs is None:
            raise ConnectorError(f"{self.company}: unexpected greenhouse response shape (no 'jobs' key)")

        return [
            Job(
                company=self.company,
                job_id=str(j["id"]),
                title=j.get("title", ""),
                url=j.get("absolute_url", ""),
                location=(j.get("location") or {}).get("name", ""),
            )
            for j in jobs
        ]
