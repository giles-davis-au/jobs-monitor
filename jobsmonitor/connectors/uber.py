from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.models import Job

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MAX_PAGES = 100  # sanity cap (685 jobs / 10 per page ~= 69 pages today)


class UberConnector:
    """Uber's careers site sits behind Cloudflare, so — like Canva — this
    needs a real browser. Unlike Canva, the underlying API
    (jobs.uber.com/api/jobs/search/) has no server-side location filter that
    can silently degrade: it always returns every job globally, so we fetch
    everything and let matcher.py do the Sydney filtering, same as most
    other connectors. Each page is a plain `fetch()` executed inside the
    already-loaded browser tab (reusing its Cloudflare clearance) rather
    than a full page navigation per page, which is much faster across ~69
    pages.
    """

    def __init__(self, company: str = "Uber", base_url: str = "https://www.uber.com/us/en/careers/list/"):
        self.company = company
        self.base_url = base_url

    def fetch(self) -> list[Job]:
        raw_jobs = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(self.base_url, wait_until="networkidle", timeout=30000)
                    page.wait_for_timeout(1000)

                    total_pages = None
                    page_num = 1
                    while total_pages is None or page_num <= total_pages:
                        result = page.evaluate(
                            """(pageNum) => fetch(`https://jobs.uber.com/api/jobs/search/?page=${pageNum}`,"""
                            """ {credentials: 'include'}).then(r => r.json())""",
                            page_num,
                        )
                        if total_pages is None:
                            total_pages = result.get("totalPages") or 1
                        batch = result.get("jobs") or []
                        if not batch:
                            break
                        raw_jobs.extend(batch)
                        page_num += 1
                        if page_num > MAX_PAGES:
                            break
                finally:
                    browser.close()
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            raise ConnectorError(f"{self.company}: uber fetch failed: {e}") from e

        return [self._parse_job(j) for j in raw_jobs]

    def _parse_job(self, j: dict) -> Job:
        locations = j.get("Locations") or []
        location_text = "; ".join(
            ", ".join(part for part in (loc.get("City"), loc.get("Region"), loc.get("Country")) if part)
            for loc in locations
        )
        url_path = (j.get("Urls") or [{}])[0].get("Url", "")

        return Job(
            company=self.company,
            job_id=str(j.get("Id", "")),
            title=j.get("Title", ""),
            # NOTE: the advert lives on jobs.uber.com, not www.uber.com — the
            # latter 404s on this same relative path despite being the site
            # we navigate to fetch the API from. Confirmed by hand: a bare
            # www.uber.com URL doesn't just 404, an AU-based client following
            # it gets redirected into a broken doubled-locale path
            # (.../au/en/en/jobs/{id}/).
            url=f"https://jobs.uber.com{url_path}",
            location=location_text,
        )
