import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

PAGE_SIZE = 20
MAX_PAGES = 40  # sanity cap (~800 jobs)


class WorkdayConnector:
    """Generic connector for companies on Workday's recruiting site (CXS API).

    Find `tenant`/`wd_host`/`site` from a job link on the company's Workday
    careers page, e.g. `https://relx.wd3.myworkdayjobs.com/en-US/LexisNexisLegal/...`
    -> tenant=relx, wd_host=wd3, site=LexisNexisLegal.

    Workday's search response gives `locationsText` (often vague for
    multi-location postings, e.g. "3 Locations") but `externalPath` usually
    embeds the primary location as a URL slug (e.g.
    "/job/Australia---Sydney/..."), so we fold both into the location text
    handed to the matcher rather than relying on `locationsText` alone.
    """

    def __init__(self, company: str, tenant: str, wd_host: str, site: str):
        self.company = company
        self.tenant = tenant
        self.wd_host = wd_host
        self.site = site

    def fetch(self) -> list[Job]:
        base = f"https://{self.tenant}.{self.wd_host}.myworkdayjobs.com"
        api_url = f"{base}/wday/cxs/{self.tenant}/{self.site}/jobs"

        postings = []
        try:
            with http_client() as client:
                # Workday's API only reports an accurate `total` on the very
                # first page — later pages in the same session report 0 even
                # though job data keeps flowing normally. So we trust `total`
                # only from page one, and otherwise treat "got fewer than a
                # full page" as the real end-of-results signal.
                total = None
                offset = 0
                for _ in range(MAX_PAGES):
                    resp = client.post(
                        api_url,
                        json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    if total is None:
                        total = data["total"]
                    batch = data["jobPostings"]
                    if not batch:
                        break
                    postings.extend(batch)
                    offset += PAGE_SIZE
                    if len(batch) < PAGE_SIZE or (total and offset >= total):
                        break
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ConnectorError(f"{self.company}: workday fetch failed: {e}") from e

        jobs = []
        for p in postings:
            external_path = p.get("externalPath", "")
            location = f"{p.get('locationsText', '')} {external_path}".strip()
            jobs.append(
                Job(
                    company=self.company,
                    job_id=external_path or p.get("title", ""),
                    title=p.get("title", ""),
                    url=f"{base}/{self.site}{external_path}",
                    location=location,
                )
            )
        return jobs
