import re

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

MAX_PAGES = 20  # sanity cap


class TeamtailorConnector:
    """Generic connector for companies on Teamtailor's default career-site
    template (fully server-rendered HTML, no JS execution needed).

    Confirmed against Tyro's `/jobs` page — the default template markup
    (`ul#jobs_list_container`) is Teamtailor's own, so this should work
    unchanged for any other company using the stock template. Paginates via
    `?page=N` while the declared total exceeds what's been collected.
    """

    def __init__(self, company: str, base_url: str):
        self.company = company
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with http_client() as client:
                total = None
                for page_num in range(1, MAX_PAGES + 1):
                    resp = client.get(f"{self.base_url}/jobs", params={"page": page_num})
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    if total is None:
                        total = self._parse_total(soup)

                    items = soup.select("ul#jobs_list_container > li")
                    if total > 0 and not items:
                        raise ConnectorError(
                            f"{self.company}: teamtailor page reports {total} jobs but no list "
                            "items found — page structure may have changed"
                        )

                    jobs.extend(self._parse_item(item) for item in items)

                    if not items or len(jobs) >= total:
                        break
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: teamtailor fetch failed: {e}") from e

        return jobs

    def _parse_total(self, soup: BeautifulSoup) -> int:
        for heading in soup.select("h2"):
            match = re.search(r"(\d+)\s+jobs?\b", heading.get_text(), re.IGNORECASE)
            if match:
                return int(match.group(1))
        raise ConnectorError(
            f"{self.company}: teamtailor jobs-count heading not found — page structure may have changed"
        )

    def _parse_item(self, item) -> Job:
        link = item.select_one("a")
        url = link["href"] if link and link.has_attr("href") else ""
        title = link.get_text(strip=True) if link else ""
        detail = item.select_one(".mt-1")
        location = detail.get_text(separator=" ", strip=True) if detail else ""
        job_id = url.rsplit("/", 1)[-1] if url else title

        return Job(company=self.company, job_id=job_id, title=title, url=url, location=location)
