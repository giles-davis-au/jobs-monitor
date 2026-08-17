import math
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
PAGE_SIZE = 12
MAX_PAGES = 20  # sanity cap; also the point past which TikTok's pager may
# switch to an ellipsis layout that this connector doesn't handle


class TikTokConnector:
    """TikTok's careers site (lifeattiktok.com) has no usable public API —
    the one "public" endpoint returns a fixed small sample with no working
    pagination or filters. Real search results only appear when the search
    UI is driven properly: filling the search box and clicking "Search now"
    (typing alone, or navigating directly to the resulting URL with
    `offset=N`, does NOT work — confirmed the offset query param is ignored
    on direct navigation and only takes effect when the numbered page
    button is actually clicked). This makes this the most fragile connector
    in the system: it depends on a specific multi-step UI flow rather than
    a single request, and will need attention if TikTok changes their
    search page's layout, button text, or CSS structure.
    """

    def __init__(self, company: str = "TikTok", search_term: str = "Sydney"):
        self.company = company
        self.search_term = search_term

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto("https://lifeattiktok.com/search", wait_until="load", timeout=45000)
                    page.wait_for_timeout(2000)

                    for label in ("Decline all", "Accept all"):
                        try:
                            page.click(f"text={label}", timeout=3000)
                            break
                        except PlaywrightTimeoutError:
                            continue

                    page.fill('input[placeholder="Enter Title, Skill, or City"]', self.search_term)
                    page.click("text=Search now")
                    page.wait_for_timeout(2500)

                    total = self._parse_total(page)
                    num_pages = min(math.ceil(total / PAGE_SIZE), MAX_PAGES) if total else 0

                    for page_num in range(1, num_pages + 1):
                        if page_num > 1:
                            page.get_by_role("button", name=str(page_num), exact=True).click()
                            page.wait_for_timeout(2000)
                        jobs.extend(self._scrape_current_page(page))
                finally:
                    browser.close()
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            raise ConnectorError(f"{self.company}: tiktok fetch failed: {e}") from e

        if total and not jobs:
            raise ConnectorError(
                f"{self.company}: page reported {total} open roles but none were scraped "
                "— page structure may have changed"
            )
        return jobs

    def _parse_total(self, page) -> int:
        text = page.inner_text("body")
        match = re.search(r"(\d+)\s+open roles", text)
        if not match:
            raise ConnectorError(
                f"{self.company}: open-roles count not found — page structure may have changed"
            )
        return int(match.group(1))

    def _scrape_current_page(self, page) -> list[Job]:
        cards = page.eval_on_selector_all(
            '.job-list-container a[href*="/search/"]',
            "els => els.map(e => ({href: e.href, text: e.innerText}))",
        )
        return [self._parse_card(c) for c in cards]

    def _parse_card(self, card: dict) -> Job:
        lines = [line.strip() for line in card["text"].split("\n") if line.strip()]
        title = lines[0] if lines else ""
        # remaining lines are location / department / employment-type chips —
        # fold them all in so matcher.py can find "Sydney" regardless of order
        location = "; ".join(lines[1:])
        href = card["href"]
        job_id = href.rsplit("/", 1)[-1]

        return Job(company=self.company, job_id=job_id, title=title, url=href, location=location)
