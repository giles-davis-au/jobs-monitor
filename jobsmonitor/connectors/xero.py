import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.models import Job

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
MAX_PAGES = 20  # sanity cap
AUSTRALIA_FRACTION_THRESHOLD = 0.9


class XeroConnector:
    """Xero's careers.xero.com runs the same Umbraco job-board platform as
    Canva (same `div.card.card-job` markup, same Cloudflare JS bot-challenge
    that needs a real browser) — confirmed live, just a different base URL
    and a different "N of M" results-count phrasing ("Displaying 1 to 20 of
    44 matching jobs" vs Canva's "of 123 Live Results").

    Same silent-degradation risk as Canva: a lower-trust automated
    environment could get an unfiltered response despite the country
    filter, so every fetch validates the results are plausibly
    Australia-filtered before trusting them.
    """

    def __init__(self, company: str = "Xero", base_url: str = "https://careers.xero.com"):
        self.company = company
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    total = None

                    for page_num in range(1, MAX_PAGES + 1):
                        url = (
                            f"{self.base_url}/jobs/?orderby=0&pagesize=20"
                            f"&page={page_num}&radius=100&country=Australia"
                        )
                        page.goto(url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1000)

                        if total is None:
                            total = self._parse_total(page)

                        cards = page.locator("div.card.card-job")
                        count = cards.count()
                        if count == 0:
                            break

                        for i in range(count):
                            card = cards.nth(i)
                            link = card.locator("a.js-view-job")
                            jobs.append(
                                self.build_job(
                                    job_id=card.get_attribute("data-id"),
                                    title=link.inner_text(),
                                    href=link.get_attribute("href") or "",
                                    location_text=card.locator(".job-meta").inner_text(),
                                )
                            )

                        if len(jobs) >= total:
                            break
                finally:
                    browser.close()
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            raise ConnectorError(f"{self.company}: xero fetch failed: {e}") from e

        self.validate_australia_filter_applied(jobs)
        return jobs

    def _parse_total(self, page) -> int:
        return self.parse_total_from_text(page.locator("#results").inner_text())

    def parse_total_from_text(self, text: str) -> int:
        match = re.search(r"of\s+(\d+)\s+matching jobs", text, re.IGNORECASE)
        if not match:
            raise ConnectorError(
                f"{self.company}: results-count text not found — page structure may have changed"
            )
        return int(match.group(1))

    def build_job(self, job_id: str | None, title: str, href: str, location_text: str) -> Job:
        url = href if href.startswith("http") else f"{self.base_url}{href}"
        return Job(
            company=self.company,
            job_id=job_id or url,
            title=title,
            url=url,
            location=location_text.replace("\n", ", "),
        )

    def validate_australia_filter_applied(self, jobs: list[Job]) -> None:
        if not jobs:
            return
        au_count = sum(1 for j in jobs if "australia" in j.location.lower())
        fraction = au_count / len(jobs)
        if fraction < AUSTRALIA_FRACTION_THRESHOLD:
            raise ConnectorError(
                f"{self.company}: country filter does not appear to have applied — only "
                f"{au_count}/{len(jobs)} results mention Australia. This usually means "
                "Cloudflare served a degraded, unfiltered response rather than a real "
                "page-structure change."
            )
