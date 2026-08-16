import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

LISTINGS_URL = "https://www.atlassian.com/endpoint/careers/listings"


class AtlassianConnector:
    """Atlassian's own (undocumented, first-party) careers JSON endpoint.

    Confirmed live via browser network inspection: the site's location/team
    filters are applied client-side in the browser — the endpoint itself
    always returns every open role worldwide. We fetch everything and let
    matcher.py do the Sydney filtering, same as every other connector.
    """

    def __init__(self, company: str = "Atlassian"):
        self.company = company

    def fetch(self) -> list[Job]:
        try:
            with http_client() as client:
                resp = client.get(LISTINGS_URL)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ConnectorError(f"{self.company}: atlassian fetch failed: {e}") from e

        if not isinstance(data, list):
            raise ConnectorError(f"{self.company}: unexpected atlassian response shape (expected a list)")

        result = []
        for j in data:
            locations = j.get("locations") or []
            location_text = "; ".join(loc for loc in locations if loc)

            result.append(
                Job(
                    company=self.company,
                    job_id=str(j["id"]),
                    title=j.get("title", ""),
                    url=self._advert_url(j),
                    location=location_text,
                )
            )
        return result

    def _advert_url(self, j: dict) -> str:
        """`applyUrl` drops the visitor straight into the application flow
        (`?mode=apply`) rather than the job advert. `portalJobPost.portalUrl`
        is the same iCIMS URL without that param — use it when present, and
        fall back to stripping `?mode=apply` off `applyUrl` otherwise.
        """
        portal_url = (j.get("portalJobPost") or {}).get("portalUrl")
        if portal_url:
            return portal_url
        apply_url = j.get("applyUrl", "")
        return apply_url.split("?mode=apply")[0] if apply_url else ""
