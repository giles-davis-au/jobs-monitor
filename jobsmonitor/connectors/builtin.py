import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job


class BuiltInConnector:
    """Connector for a single company's listing on a Built In city site
    (e.g. builtinsydney.au) — fully server-rendered HTML, no JS execution
    needed, and no pagination since these are single-company result sets.

    Unlike every other connector in this project, Built In is a third-party
    job board that indexes a company's postings itself rather than the
    company's own careers page — used only for companies (e.g. Airtasker)
    whose own site actively blocks automated access (Cloudflare Turnstile).
    That means results here can lag behind or diverge slightly from the
    company's real listings, but it's better than no coverage at all.

    Find `company_id` from the site's own company-filtered jobs URL, e.g.
    `https://builtinsydney.au/jobs?companyId=194323&allLocations=true`.

    The site itself is city-scoped (a "Built In Sydney" listing), so every
    result is already Sydney-relevant by construction — no need to scrape
    or parse a per-job location field.
    """

    def __init__(self, company: str, base_url: str, company_id: str):
        self.company = company
        self.base_url = base_url.rstrip("/")
        self.company_id = company_id

    def fetch(self) -> list[Job]:
        url = f"{self.base_url}/jobs?companyId={self.company_id}&allLocations=true"
        try:
            with http_client() as client:
                resp = client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: builtin fetch failed: {e}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select('[data-id="job-card"]')
        if not cards:
            raise ConnectorError(f"{self.company}: no job cards found — page structure may have changed")

        return [self._parse_card(c) for c in cards]

    def _parse_card(self, card) -> Job:
        title_el = card.select_one('a[data-id="job-card-title"]')
        title = title_el.get_text(strip=True) if title_el else ""
        href = title_el["href"] if title_el and title_el.has_attr("href") else ""
        url = f"{self.base_url}{href}"
        job_id = href.rsplit("/", 1)[-1] if href else url

        return Job(company=self.company, job_id=job_id, title=title, url=url, location="Sydney")
