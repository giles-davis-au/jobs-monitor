import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.oraclehcm import PAGE_SIZE, OracleHcmConnector
from jobsmonitor.connectors.payau import PayAuConnector
from jobsmonitor.connectors.rippling import RipplingConnector
from jobsmonitor.matcher import classify_location
from jobsmonitor.models import LocationConfidence
from tests.conftest import load_json_fixture

PEPPER = ("Pepper Money", "https://edss.fa.ap1.oraclecloud.com", "CX_1001")


def test_oraclehcm_parses_fixture_with_real_location_variants(mock_get):
    mock_get.returns(httpx.Response(200, json=load_json_fixture("oraclehcm_pepper.json")))

    jobs = {j.job_id: j for j in OracleHcmConnector(*PEPPER).fetch()}

    assert len(jobs) == 4
    assert jobs["468"].title == "Team Leader - Customer Resolutions"
    assert jobs["468"].url == (
        "https://edss.fa.ap1.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/468"
    )
    # Real location shapes seen live, through the real matcher: a suburb
    # resolves to a city, a bare state is flagged country-level (over-catch,
    # not dropped), and another city is excluded.
    assert classify_location(jobs["468"].location) == LocationConfidence.CITY
    assert classify_location(jobs["393"].location) == LocationConfidence.COUNTRY_ONLY
    assert classify_location(jobs["438"].location) == LocationConfidence.COUNTRY_ONLY
    assert classify_location(jobs["449"].location) is None


def test_oraclehcm_paginates_until_total_reached(mock_get):
    def page(ids, total):
        reqs = [{"Id": str(i), "Title": f"Job {i}", "PrimaryLocation": "NSW, Australia"} for i in ids]
        return httpx.Response(200, json={"items": [{"TotalJobsCount": total, "requisitionList": reqs}]})

    mock_get.returns(page(range(PAGE_SIZE), PAGE_SIZE + 3))
    mock_get.returns(page(range(PAGE_SIZE, PAGE_SIZE + 3), PAGE_SIZE + 3))

    jobs = OracleHcmConnector(*PEPPER).fetch()

    assert len(jobs) == PAGE_SIZE + 3
    assert len(mock_get.calls) == 2


def test_oraclehcm_folds_secondary_locations_in(mock_get):
    req = {
        "Id": "1",
        "Title": "Role",
        "PrimaryLocation": "VIC, Australia",
        "secondaryLocations": [{"Name": "Sydney, NSW, Australia"}, {}],
    }
    mock_get.returns(httpx.Response(200, json={"items": [{"TotalJobsCount": 1, "requisitionList": [req]}]}))

    (job,) = OracleHcmConnector(*PEPPER).fetch()

    assert job.location == "VIC, Australia; Sydney, NSW, Australia"


def test_oraclehcm_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"items": []}))
    with pytest.raises(ConnectorError):
        OracleHcmConnector(*PEPPER).fetch()


def test_rippling_parses_fixture(mock_get):
    mock_get.returns(httpx.Response(200, json=load_json_fixture("rippling_monoova.json")))

    jobs = RipplingConnector("Monoova", "monoova-services-pty-ltd").fetch()

    assert len(jobs) == 5
    by_title = {j.title: j for j in jobs}
    em = by_title["Engineering Manager"]
    assert em.location == "Sydney, Australia"
    assert em.url == (
        "https://ats.rippling.com/monoova-services-pty-ltd/jobs/c3eeda5e-78d3-447d-8ef8-6498f22efb65"
    )
    assert em.job_id == "c3eeda5e-78d3-447d-8ef8-6498f22efb65"


def test_rippling_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"error": "board not found"}))
    with pytest.raises(ConnectorError):
        RipplingConnector("Monoova", "nope").fetch()


def test_rippling_wraps_http_errors(mock_get):
    mock_get.raises(httpx.ConnectError("boom"))
    with pytest.raises(ConnectorError):
        RipplingConnector("Monoova", "monoova-services-pty-ltd").fetch()


# pay.com.au listed zero roles when this connector was written, so there is no
# real populated page to capture: the empty block below is the real live
# markup, and the populated one is SYNTHETIC (links inside the same block).
PAYAU_EMPTY_BLOCK = """
<div class="jobs-listing-block">
    <div class="job-role-innner-container">
                    </div>
</div>
"""

PAYAU_SYNTHETIC_ROLES = """
<div class="jobs-listing-block"><div class="job-role-innner-container">
  <a href="/careers/senior-engineer/">Senior Engineer</a>
  <a href="https://pay.com.au/careers/ops-lead/"><h3>Operations Lead</h3></a>
  <a href="/careers/"> </a>
</div></div>
"""


def test_payau_real_empty_listing_means_zero_jobs():
    assert PayAuConnector().parse_jobs(PAYAU_EMPTY_BLOCK) == []


def test_payau_parses_roles_and_reports_country_level_location():
    jobs = PayAuConnector().parse_jobs(PAYAU_SYNTHETIC_ROLES)

    assert [j.title for j in jobs] == ["Senior Engineer", "Operations Lead"]  # blank-text link skipped
    assert jobs[0].url == "https://pay.com.au/careers/senior-engineer/"
    assert jobs[1].url == "https://pay.com.au/careers/ops-lead/"
    # over-catch by design: no per-role location, so flagged "verify city"
    assert all(classify_location(j.location) == LocationConfidence.COUNTRY_ONLY for j in jobs)


def test_payau_raises_when_listing_block_missing():
    with pytest.raises(ConnectorError):
        PayAuConnector().parse_jobs("<html><body>redesigned page</body></html>")


def test_payau_raises_when_block_has_content_but_no_links():
    html = '<div class="jobs-listing-block"><div>Product Manager — Sydney</div></div>'
    with pytest.raises(ConnectorError):
        PayAuConnector().parse_jobs(html)


def test_payau_fetch_uses_parse(mock_get):
    mock_get.returns(httpx.Response(200, text=PAYAU_EMPTY_BLOCK))
    assert PayAuConnector().fetch() == []
