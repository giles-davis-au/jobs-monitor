import re

import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class ZipConnector:
    """One-off connector for Zip Co's careers page — fully server-rendered
    HTML, no JS execution needed. The page's own CSS class names look like
    generated/hashed CSS-module classes that will likely change on
    redeploy, so this deliberately avoids selecting by class and instead
    anchors on `a[href^="/careers/roles/"]`, which is a stable, semantic
    link pattern.
    """

    def __init__(self, company: str = "Zip", base_url: str = "https://zip.co"):
        self.company = company
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[Job]:
        try:
            with http_client() as client:
                resp = client.get(f"{self.base_url}/careers/roles")
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: zip fetch failed: {e}") from e

        total = self._parse_total(soup)
        links = soup.select('a[href^="/careers/roles/"]')

        if total > 0 and not links:
            raise ConnectorError(
                f"{self.company}: page reports {total} roles but no role links found "
                "— page structure may have changed"
            )

        return [self._parse_link(link) for link in links]

    def _parse_total(self, soup: BeautifulSoup) -> int:
        match = re.search(r"(\d+)\s+roles?\b", soup.get_text(), re.IGNORECASE)
        if not match:
            raise ConnectorError(
                f"{self.company}: roles-count text not found — page structure may have changed"
            )
        return int(match.group(1))

    def _parse_link(self, link) -> Job:
        title_el = link.select_one("h3")
        title = title_el.get_text(strip=True) if title_el else ""

        location_el = link.select_one("ul li")
        location = location_el.get_text(strip=True) if location_el else ""

        href = link.get("href", "")
        job_id = href.rsplit("/", 1)[-1] if href else title
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        return Job(company=self.company, job_id=job_id, title=title, url=url, location=location)
