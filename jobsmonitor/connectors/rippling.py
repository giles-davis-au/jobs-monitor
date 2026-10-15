import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class RipplingConnector:
    """Generic connector for companies hiring through Rippling's ATS
    (`ats.rippling.com/{board}/jobs`).

    Uses Rippling's public job-board endpoint, which returns every open role
    as one flat JSON list — no pagination (confirmed live: its count matched
    the newer paginated v2 endpoint's totalItems). Find `board` from the
    company's job links, e.g. `https://ats.rippling.com/monoova-services-pty-ltd/jobs/...`
    -> board=monoova-services-pty-ltd.
    """

    def __init__(self, company: str, board: str):
        self.company = company
        self.board = board

    def fetch(self) -> list[Job]:
        url = f"https://api.rippling.com/platform/api/ats/v1/board/{self.board}/jobs"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
                items = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: rippling fetch failed: {e}") from e

        if not isinstance(items, list):
            raise ConnectorError(f"{self.company}: unexpected rippling response shape: {type(items).__name__}")

        return [self._parse_item(item) for item in items]

    def _parse_item(self, item: dict) -> Job:
        job_id = str(item.get("uuid", ""))
        return Job(
            company=self.company,
            job_id=job_id,
            title=item.get("name", ""),
            url=item.get("url") or f"https://ats.rippling.com/{self.board}/jobs/{job_id}",
            location=(item.get("workLocation") or {}).get("label", ""),
        )
