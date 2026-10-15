import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

PAGE_SIZE = 25
MAX_PAGES = 40  # sanity cap (~1000 jobs)


class OracleHcmConnector:
    """Generic connector for companies on Oracle HCM Cloud's Candidate
    Experience careers sites (`{host}.fa.{region}.oraclecloud.com`).

    The careers UI is a JS app, but it's backed by a public, unauthenticated
    REST endpoint (`recruitingCEJobRequisitions`) — confirmed live, no
    browser needed. Find `base_url` and `site` from the careers URL, e.g.
    `https://edss.fa.ap1.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs`
    -> base_url=https://edss.fa.ap1.oraclecloud.com, site=CX_1001.

    No location filter is applied here — everything the site lists comes
    back and the matcher does the Sydney filtering. Oracle often gives only
    a state ("NSW, Australia") rather than a city, which the matcher treats
    as country-level and flags "verify city" rather than dropping.
    """

    def __init__(self, company: str, base_url: str, site: str):
        self.company = company
        self.base_url = base_url.rstrip("/")
        self.site = site

    def fetch(self) -> list[Job]:
        api_url = f"{self.base_url}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        requisitions: list[dict] = []

        try:
            with http_client() as client:
                for page in range(MAX_PAGES):
                    resp = client.get(
                        api_url,
                        params={
                            "onlyData": "true",
                            "expand": "requisitionList.secondaryLocations",
                            "finder": (
                                f"findReqs;siteNumber={self.site},limit={PAGE_SIZE},"
                                f"offset={page * PAGE_SIZE},sortBy=POSTING_DATES_DESC"
                            ),
                        },
                    )
                    resp.raise_for_status()
                    result = resp.json()["items"][0]
                    batch = result["requisitionList"]
                    requisitions.extend(batch)
                    if not batch or len(requisitions) >= result["TotalJobsCount"]:
                        break
        except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
            raise ConnectorError(f"{self.company}: oracle hcm fetch failed: {e}") from e

        return [self._parse_requisition(r) for r in requisitions]

    def _parse_requisition(self, r: dict) -> Job:
        job_id = str(r.get("Id", ""))

        # secondaryLocations was empty for every job seen live, so its field
        # names are unconfirmed — read defensively rather than assume.
        locations = [r.get("PrimaryLocation")]
        locations += [s.get("Name") for s in r.get("secondaryLocations") or []]
        location = "; ".join(loc for loc in locations if loc)

        return Job(
            company=self.company,
            job_id=job_id,
            title=r.get("Title", ""),
            url=f"{self.base_url}/hcmUI/CandidateExperience/en/sites/{self.site}/job/{job_id}",
            location=location,
        )
