import re

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

MAX_PAGES = 20  # sanity cap; a Sydney-filtered result set should never need this many


class AttraxConnector:
    """Generic connector for companies on the Attrax careers-site platform
    (fully server-rendered HTML, no JS execution needed).

    `filter_query` should be whatever query string the site's own location
    filter produces (e.g. Wise's Sydney filter is `options=292`) — copy it
    from the site's UI rather than guessing, since Attrax's filter IDs are
    opaque per-tenant values.

    Self-checks the page structure on every fetch: if the "N results" counter
    element is missing, or it claims N>0 results but we parsed zero tiles,
    that means the site's markup changed under us — raise rather than
    silently return an empty list (see docs/PLAN.md §6).
    """

    def __init__(self, company: str, base_url: str, filter_query: str):
        self.company = company
        self.base_url = base_url.rstrip("/")
        self.filter_query = filter_query

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with http_client() as client:
                for page in range(1, MAX_PAGES + 1):
                    url = f"{self.base_url}/jobs?{self.filter_query}&page={page}"
                    resp = client.get(url)
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    total = self._parse_total_results(soup)
                    tiles = soup.select("div.attrax-vacancy-tile")

                    if total > 0 and not tiles:
                        raise ConnectorError(
                            f"{self.company}: attrax page reports {total} results but no "
                            "job tiles were found — page structure may have changed"
                        )

                    jobs.extend(self._parse_tile(t) for t in tiles)

                    if not tiles or len(jobs) >= total:
                        break
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: attrax fetch failed: {e}") from e

        return jobs

    def _parse_total_results(self, soup: BeautifulSoup) -> int:
        el = soup.select_one(".attrax-pagination__total-results")
        if el is None:
            raise ConnectorError(
                f"{self.company}: attrax results-count element not found — page structure may have changed"
            )
        match = re.search(r"\d+", el.get_text())
        return int(match.group()) if match else 0

    def _parse_tile(self, tile) -> Job:
        title_el = tile.select_one("a.attrax-vacancy-tile__title")
        title = title_el.get_text(strip=True) if title_el else ""
        href = title_el["href"] if title_el and title_el.has_attr("href") else ""
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        location_el = tile.select_one(".attrax-vacancy-tile__location-freetext .attrax-vacancy-tile__item-value")
        location = location_el.get_text(strip=True) if location_el else ""

        return Job(
            company=self.company,
            job_id=tile.get("data-jobid", url),
            title=title,
            url=url,
            location=location,
        )
