from bs4 import BeautifulSoup
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


class ElmoConnector:
    """Generic connector for companies on ELMO Talent's recruitment career
    portal (an AngularJS app — job listings are rendered client-side, so this
    needs Playwright rather than a plain HTTP request; the initial HTML is
    just an empty app shell).

    Find `elmo_subdomain` from the company's own careers page — it embeds
    the portal via an iframe pointing at
    `https://{elmo_subdomain}.elmotalent.com.au/careers/default/jobs?layout=iframe`.

    Paginates via `&page=N`, stopping once a page returns no job cards.
    """

    def __init__(self, company: str, elmo_subdomain: str):
        self.company = company
        self.elmo_subdomain = elmo_subdomain

    def fetch(self) -> list[Job]:
        base = f"https://{self.elmo_subdomain}.elmotalent.com.au"
        jobs: list[Job] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    for page_num in range(1, MAX_PAGES + 1):
                        url = f"{base}/careers/default/jobs?layout=iframe&page={page_num}"
                        page.goto(url, wait_until="networkidle", timeout=30000)
                        page.wait_for_timeout(1500)
                        soup = BeautifulSoup(page.content(), "html.parser")
                        cards = soup.select("#section-list ul.list-group li.list-group-item")
                        if not cards:
                            break
                        jobs.extend(self._parse_card(c, base) for c in cards)
                finally:
                    browser.close()
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            raise ConnectorError(f"{self.company}: elmo fetch failed: {e}") from e

        return jobs

    def _parse_card(self, card, base: str) -> Job:
        link = card.select_one("a.redirect_elmo_link")
        title = link.get_text(strip=True) if link else ""
        href = link.get("href", "") if link else ""
        url = href if href.startswith("http") else f"{base}{href}"

        # No class/data-id identifies the location text itself — it's the
        # element two levels up from the location-pin icon's sibling column.
        icon = card.select_one(".glyphicon-map-marker")
        location = ""
        if icon:
            location_col = icon.parent.parent.find_next_sibling("div")
            location = location_col.get_text(strip=True) if location_col else ""

        return Job(company=self.company, job_id=href or url, title=title, url=url, location=location)
