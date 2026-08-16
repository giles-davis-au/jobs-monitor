import httpx

from jobsmonitor.connectors.base import ConnectorError, http_client
from jobsmonitor.models import Job

BASE_URL = "https://ats-cdn.ehrocks.com/ats/api/v1/embedded/widget"


class EmploymentHeroConnector:
    """Employment Hero's own in-house ATS product ('EH Recruitment'), which
    they dogfood for their own careers page.

    Confirmed live by reading their embed widget's compiled JS
    (addons-assets.employmenthero.com/jobs-widget/v1/widget.js), which builds
    `{BASE_URL}/organisations/{org_id}/jobs?page_index=N`. The org id comes
    from the `data-org-id` attribute on the embed `<script>` tag on the
    careers page — find it there for any other company using this widget.
    """

    def __init__(self, company: str, org_id: str):
        self.company = company
        self.org_id = org_id

    def fetch(self) -> list[Job]:
        try:
            with http_client() as client:
                all_items = []
                page = 1
                total_pages = 1
                while page <= total_pages:
                    url = f"{BASE_URL}/organisations/{self.org_id}/jobs?page_index={page}"
                    resp = client.get(url)
                    resp.raise_for_status()
                    payload = resp.json()
                    data = payload["data"]
                    all_items.extend(data["items"])
                    total_pages = data["total_pages"]
                    page += 1
        except (httpx.HTTPError, ValueError, KeyError) as e:
            raise ConnectorError(f"{self.company}: employment hero fetch failed: {e}") from e

        return [
            Job(
                company=self.company,
                job_id=item["id"],
                title=item.get("title", ""),
                url=item.get("application_url", ""),
                location=item.get("vendor_location_name") or "",
            )
            for item in all_items
        ]
