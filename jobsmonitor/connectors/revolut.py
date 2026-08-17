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


class RevolutConnector:
    """Revolut's careers site is a custom-built Next.js app (no third-party
    ATS). Plain HTTP requests get a stripped-down HTML variant with no job
    data embedded — confirmed the same URL returns the full page (including
    a `__NEXT_DATA__` script tag with every position) to a real browser but
    not to curl/httpx, similar to the bot-trust degradation seen elsewhere
    in this project. So this needs Playwright.

    Deliberately reads `__NEXT_DATA__` from the live-rendered page rather
    than constructing a `/_next/data/{buildId}/...` URL directly — that
    buildId rotates on every Revolut deployment, so a hardcoded one would
    silently break; reading it from the page each time is self-updating.

    Job URLs need a `{slug}-{uuid}` path, but confirmed live that only the
    trailing UUID is actually used for routing — an arbitrary/wrong slug
    still resolves to the correct job — so the slugify here doesn't need to
    exactly match Revolut's own algorithm, just be a reasonable label.
    """

    def __init__(self, company: str = "Revolut", url: str = "https://www.revolut.com/en-AU/careers/"):
        self.company = company
        self.url = url

    def fetch(self) -> list[Job]:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page(user_agent=USER_AGENT)
                    page.goto(self.url, wait_until="networkidle", timeout=30000)
                    data = page.evaluate(
                        "() => JSON.parse(document.getElementById('__NEXT_DATA__').textContent)"
                    )
                finally:
                    browser.close()
        except (PlaywrightError, PlaywrightTimeoutError) as e:
            raise ConnectorError(f"{self.company}: revolut fetch failed: {e}") from e

        try:
            positions = data["props"]["pageProps"]["positions"]
        except (KeyError, TypeError) as e:
            raise ConnectorError(f"{self.company}: unexpected page data shape: {e}") from e

        return [self._parse_position(p) for p in positions]

    def _parse_position(self, p: dict) -> Job:
        title = p.get("text", "")
        job_id = p.get("id", "")
        slug = self._slugify(title)
        url = f"https://www.revolut.com/en-AU/careers/position/{slug}-{job_id}/"

        locations = p.get("locations") or []
        location = "; ".join(loc.get("name", "") for loc in locations if loc.get("name"))

        return Job(company=self.company, job_id=job_id, title=title, url=url, location=location)

    def _slugify(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
