import re

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

MAX_PAGES = 10  # sanity cap


class AirwallexConnector:
    """One-off connector for Airwallex's careers site: WordPress + Elementor
    Pro "Loop Grid" with a custom `location`/`country` taxonomy.

    Each job card (`div[data-elementor-type="loop-item"]`) carries its own
    location as CSS class tokens (e.g. `location-sydney`, `country-australia`)
    — we read those directly rather than trying to parse free text, same
    pattern as the Wise/Attrax connector.

    The Elementor loop-grid widget id ('9075d2b') is baked into the page's
    own pagination query param name (`e-page-9075d2b`) — if Airwallex
    rebuilds this page in Elementor, that id will change and pagination
    beyond page 1 will silently stop working, so this is the most likely
    part of this connector to need updating over time.
    """

    WIDGET_ID = "9075d2b"

    def __init__(self, company: str = "Airwallex", base_url: str = "https://careers.airwallex.com"):
        self.company = company
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with http_client() as client:
                for page in range(1, MAX_PAGES + 1):
                    url = (
                        f"{self.base_url}/jobs/?e-page-{self.WIDGET_ID}={page}"
                        "&location%5B0%5D=sydney&order=newest"
                    )
                    resp = client.get(url)
                    resp.raise_for_status()
                    html = resp.text
                    soup = BeautifulSoup(html, "html.parser")

                    if soup.select_one(".elementor-widget-loop-grid") is None:
                        raise ConnectorError(
                            f"{self.company}: loop-grid container not found — page structure may have changed"
                        )

                    cards = soup.select('div[data-elementor-type="loop-item"]')
                    jobs.extend(self._parse_card(c) for c in cards)

                    has_next_page = f"e-page-{self.WIDGET_ID}={page + 1}" in html
                    if not cards or not has_next_page:
                        break
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: airwallex fetch failed: {e}") from e

        return jobs

    def _parse_card(self, card) -> Job:
        classes = card.get("class", [])

        post_id = next((c for c in classes if re.match(r"^post-\d+$", c)), None)
        job_id = post_id.removeprefix("post-") if post_id else ""

        title_el = card.select_one(".elementor-widget-theme-post-title .elementor-heading-title")
        title = title_el.get_text(strip=True) if title_el else ""

        link_el = card.select_one('a[href*="/job/"]')
        url = link_el["href"] if link_el and link_el.has_attr("href") else ""
        if not job_id and url:
            job_id = url  # fall back to the URL as a dedup key if no post-id class

        location_tokens = [
            c.removeprefix("location-") for c in classes if c.startswith("location-")
        ] + [c.removeprefix("country-") for c in classes if c.startswith("country-")]
        location = ", ".join(t.replace("-", " ") for t in location_tokens)

        return Job(company=self.company, job_id=job_id, title=title, url=url, location=location)
