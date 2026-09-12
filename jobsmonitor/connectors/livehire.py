import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

PAGE_SIZE = 20
MAX_PAGES = 20  # sanity cap


class LiveHireConnector:
    """Generic connector for companies on LiveHire's public careers widget.

    Two-step auth: `GET .../auth/token/{segment}` returns a short-lived
    bearer token (no API key needed — this is the same public token the
    embedded widget itself fetches), used to `POST .../search/{segment}/{page}/{pageSize}`
    for the actual job list. Find `segment` from the widget's own embed URL,
    e.g. `https://www.livehire.com/widgets/job-listings/{segment}`.
    """

    def __init__(self, company: str, segment: str):
        self.company = company
        self.segment = segment

    def fetch(self) -> list[Job]:
        base = "https://www.livehire.com"
        jobs: list[Job] = []
        try:
            with http_client() as client:
                token_resp = client.get(f"{base}/api/jobsapi/careers/auth/token/{self.segment}")
                token_resp.raise_for_status()
                token = token_resp.json()["access_token"]

                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                body = {
                    "keywords": None,
                    "categories": [],
                    "segmentCodes": [],
                    "workTypes": [],
                    "flexibleWorkOptions": [],
                    "latitude": None,
                    "longitude": None,
                    "radius": None,
                    "locationBounds": None,
                    "countryIso2": None,
                    "workLocations": [],
                    "postedFrom": None,
                    "multiSegment": False,
                }

                for page_num in range(1, MAX_PAGES + 1):
                    resp = client.post(
                        f"{base}/careers-api/search/{self.segment}/{page_num}/{PAGE_SIZE}",
                        headers=headers,
                        json=body,
                    )
                    resp.raise_for_status()
                    postings = resp.json()["jobs"]
                    if not postings:
                        break
                    jobs.extend(self._parse_posting(p) for p in postings)
                    if len(postings) < PAGE_SIZE:
                        break
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ConnectorError(f"{self.company}: livehire fetch failed: {e}") from e

        return jobs

    def _parse_posting(self, p: dict) -> Job:
        url_code = p.get("urlCode", "")
        advert_code = p.get("advertUrlCode", "")
        slug = p.get("seoSlug", "")
        url = f"https://www.livehire.com/careers/{self.segment}/job/{url_code}/{advert_code}/{slug}"

        # physicalLocation already embeds the country (e.g. "Melbourne VIC,
        # Australia") — countryName would just duplicate it.
        location = p.get("physicalLocation") or p.get("countryName") or ""

        return Job(
            company=self.company,
            job_id=advert_code or url,
            title=p.get("roleName", ""),
            url=url,
            location=location,
        )
