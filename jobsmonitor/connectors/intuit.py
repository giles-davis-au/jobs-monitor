import httpx
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

PAGE_SIZE = 15  # fixed by the site's own template, not configurable via query params
MAX_PAGES = 20  # sanity cap


class IntuitConnector:
    """Intuit's careers site runs TalentBrew (a common enterprise careers-site
    CMS) — fully server-rendered HTML for page 1, no JS execution needed.

    `location_path`/`location_type` come from TalentBrew's own location
    autocomplete API — confirmed live via
    `{base}/search-jobs/locations?term=Sydney` — and together with
    `location_slug` (a human-readable slug, only used for the URL, not
    functionally significant) build the filtered URL
    `{base}/location/{location_slug}/{org_id}/{location_path}/{location_type}`.
    `org_id` is TalentBrew's tenant id for the company (Intuit's is 27595,
    visible in every job/search URL).

    Page 2+ requires a separate AJAX endpoint (`/search-jobs/results`) that
    needs an `X-Requested-With: XMLHttpRequest` header and a `Referer` — a
    plain GET without those returns a 200 with an empty results field,
    silently looking like "no more jobs" rather than erroring. Confirmed live
    that this only actually matters once results exceed one page (15) — a
    single city the size of Sydney will rarely need it, but it's implemented
    properly rather than assumed away.
    """

    def __init__(
        self,
        company: str,
        location_slug: str,
        location_path: str,
        location_type: str,
        org_id: str = "27595",
        base_url: str = "https://jobs.intuit.com",
    ):
        self.company = company
        self.location_slug = location_slug
        self.location_path = location_path
        self.location_type = location_type
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")

    def fetch(self) -> list[Job]:
        jobs: list[Job] = []
        try:
            with http_client() as client:
                first_url = (
                    f"{self.base_url}/location/{self.location_slug}/{self.org_id}"
                    f"/{self.location_path}/{self.location_type}"
                )
                resp = client.get(first_url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")

                total = self._parse_total(soup)
                jobs.extend(self._parse_card(c) for c in soup.select("li[data-intuit-jobid]"))

                for page_num in range(2, MAX_PAGES + 1):
                    if len(jobs) >= total:
                        break
                    fragment = self._fetch_page(client, first_url, page_num, total)
                    cards = fragment.select("li[data-intuit-jobid]")
                    if not cards:
                        break
                    jobs.extend(self._parse_card(c) for c in cards)
        except httpx.HTTPError as e:
            raise ConnectorError(f"{self.company}: intuit fetch failed: {e}") from e

        return jobs

    def _fetch_page(self, client: httpx.Client, referer_url: str, page_num: int, total: int) -> BeautifulSoup:
        # Confirmed live: the site's own "Next" button sends this full param
        # set (captured via Playwright network inspection) — a trimmed-down
        # version silently returns hasContent:false with an empty results
        # string instead of erroring, so this mirrors the real request rather
        # than guessing which fields are load-bearing. FacetFilters[0].Display
        # is confirmed cosmetic-only (a placeholder value works fine).
        params = {
            "ActiveFacetID": 0,
            "CurrentPage": page_num,
            "RecordsPerPage": PAGE_SIZE,
            "TotalContentResults": "",
            "Distance": 50,
            "RadiusUnitType": 0,
            "Keywords": "",
            "Location": "",
            "ShowRadius": "False",
            "IsPagination": "False",
            "CustomFacetName": "",
            "FacetTerm": self.location_path,
            "FacetType": self.location_type,
            "FacetFilters[0].ID": self.location_path,
            "FacetFilters[0].FacetType": self.location_type,
            "FacetFilters[0].Count": total,
            "FacetFilters[0].Display": self.location_slug.replace("-", " "),
            "FacetFilters[0].IsApplied": "true",
            "FacetFilters[0].FieldName": "",
            "SearchResultsModuleName": "Search Results",
            "SearchFiltersModuleName": "Search Filters",
            "SortCriteria": 0,
            "SortDirection": 0,
            "SearchType": 3,
            "OrganizationIds": self.org_id,
            "PostalCode": "",
            "ResultsType": 1,
        }
        resp = client.get(
            f"{self.base_url}/search-jobs/results",
            params=params,
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": referer_url},
        )
        resp.raise_for_status()
        try:
            html_fragment = resp.json()["results"]
        except (KeyError, ValueError) as e:
            raise ConnectorError(f"{self.company}: unexpected pagination response shape: {e}") from e
        return BeautifulSoup(html_fragment, "html.parser")

    def _parse_total(self, soup: BeautifulSoup) -> int:
        results_section = soup.select_one("#search-results[data-total-job-results]")
        if results_section is None:
            raise ConnectorError(
                f"{self.company}: results-count attribute not found — page structure may have changed"
            )
        return int(results_section["data-total-job-results"])

    def _parse_card(self, card) -> Job:
        link = card.select_one("a.sr-item")
        title_el = link.select_one("h2") if link else None
        title = title_el.get_text(strip=True) if title_el else ""
        href = link.get("href", "") if link else ""
        url = href if href.startswith("http") else f"{self.base_url}{href}"

        location_el = link.select_one(".job-location") if link else None
        location = location_el.get_text(strip=True) if location_el else ""

        job_id = card.get("data-intuit-jobid", url)
        return Job(company=self.company, job_id=job_id, title=title, url=url, location=location)
