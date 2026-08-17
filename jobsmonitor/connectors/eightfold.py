from urllib.parse import urlparse

import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

MAX_PAGES = 100  # sanity cap


class EightfoldConnector:
    """Generic connector for companies on Eightfold.ai's careers platform
    (e.g. PayPal, CoStar Group/Domain). No Cloudflare/bot-challenge on the
    API domain itself (unlike the company's own careers.* landing page,
    which may be Cloudflare-protected) — plain HTTP works fine.

    Eightfold exposes two API generations depending on the customer, found
    by watching network requests on the company's careers page:
      - newer "pcsx" API: `https://{subdomain}.eightfold.ai/api/pcsx/search`
        -> response nested under a "data" key, job url in `positionUrl`
        (relative to the API host).
      - older "apply/v2" API: `https://{custom-domain}/api/apply/v2/jobs`
        -> flat response, job url already absolute in `canonicalPositionUrl`.
    Both take `domain` (the `?domain=` query param value on their careers
    page) and paginate via `start` (an offset, not a page number). This
    connector detects and handles either shape from the same `api_url`.

    Fetches everything unfiltered and lets matcher.py do Sydney filtering —
    Eightfold's location-filter query params expect geocoded coordinates
    and didn't reliably narrow results during testing, so it's simpler and
    more robust to filter client-side like most other connectors.
    """

    def __init__(self, company: str, api_url: str, domain: str):
        self.company = company
        self.api_url = api_url.rstrip("/")
        self.domain = domain

    def fetch(self) -> list[Job]:
        positions = []
        try:
            with http_client() as client:
                total = None
                start = 0
                for _ in range(MAX_PAGES):
                    resp = client.get(self.api_url, params={"domain": self.domain, "start": start})
                    resp.raise_for_status()
                    payload = resp.json()
                    data = payload.get("data", payload)  # pcsx nests under "data"; apply/v2 is flat
                    if total is None:
                        total = data["count"]
                    batch = data["positions"]
                    if not batch:
                        break
                    positions.extend(batch)
                    start += len(batch)
                    if start >= total:
                        break
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ConnectorError(f"{self.company}: eightfold fetch failed: {e}") from e

        return [self._build_job(p) for p in positions]

    def _build_job(self, p: dict) -> Job:
        url = p.get("canonicalPositionUrl") or self._absolute(p.get("positionUrl", ""))
        return Job(
            company=self.company,
            job_id=str(p.get("id", "")),
            title=p.get("name", ""),
            url=url,
            location="; ".join(p.get("locations") or []),
        )

    def _absolute(self, path: str) -> str:
        origin = urlparse(self.api_url)
        return f"{origin.scheme}://{origin.netloc}{path}"
