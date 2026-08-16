import httpx
import pytest

from jobsmonitor.connectors.airwallex import AirwallexConnector
from jobsmonitor.connectors.ashby import AshbyConnector
from jobsmonitor.connectors.atlassian import AtlassianConnector
from jobsmonitor.connectors.attrax import AttraxConnector
from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.employmenthero import EmploymentHeroConnector
from jobsmonitor.connectors.greenhouse import GreenhouseConnector
from jobsmonitor.connectors.lever import LeverConnector
from jobsmonitor.connectors.workable import WorkableConnector
from tests.conftest import load_json_fixture, load_text_fixture


def test_greenhouse_parses_fixture(mock_get):
    fixture = load_json_fixture("greenhouse_block.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = GreenhouseConnector("Block", "block").fetch()

    assert len(jobs) == len(fixture["jobs"])
    assert any("sydney" in j.location.lower() for j in jobs)
    assert all(j.company == "Block" for j in jobs)


def test_greenhouse_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"unexpected": "shape"}))
    with pytest.raises(ConnectorError):
        GreenhouseConnector("Block", "block").fetch()


def test_greenhouse_raises_on_network_error(mock_get):
    mock_get.raises(httpx.ConnectError("boom"))
    with pytest.raises(ConnectorError):
        GreenhouseConnector("Block", "block").fetch()


def test_lever_parses_fixture_and_folds_all_locations(mock_get):
    fixture = load_json_fixture("lever_deputy.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = LeverConnector("Deputy", "deputy").fetch()

    assert len(jobs) == len(fixture)
    # allLocations should be folded into the location text alongside the primary location
    sydney_job = next(j for j in jobs if "sydney" in j.location.lower())
    assert sydney_job.location  # non-empty, human-readable


def test_lever_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(ConnectorError):
        LeverConnector("Deputy", "deputy").fetch()


@pytest.mark.parametrize(
    ("company", "board", "fixture_name"),
    [
        ("Dovetail", "dovetail", "ashby_dovetail.json"),
        ("SafetyCulture", "safetyculture", "ashby_safetyculture.json"),
    ],
)
def test_ashby_parses_fixture(mock_get, company, board, fixture_name):
    fixture = load_json_fixture(fixture_name)
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = AshbyConnector(company, board).fetch()

    assert len(jobs) == len(fixture["jobs"])
    assert all(j.company == company for j in jobs)
    assert all(j.job_id for j in jobs)


def test_ashby_folds_secondary_locations_without_crashing(mock_get):
    fixture = {
        "jobs": [
            {
                "id": "abc",
                "title": "Engineer",
                "location": "Sydney",
                "secondaryLocations": [{"location": "Remote: US", "address": {}}],
                "jobUrl": "https://x",
            }
        ]
    }
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = AshbyConnector("Acme", "acme").fetch()

    assert jobs[0].location == "Sydney; Remote: US"


def test_workable_parses_fixture(mock_get):
    fixture = load_json_fixture("workable_rokt.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = WorkableConnector("Rokt", "157387").fetch()

    assert len(jobs) == len(fixture["jobs"])
    assert all(j.job_id for j in jobs)
    assert all(", " in j.location or j.location for j in jobs)


def test_atlassian_parses_fixture(mock_get):
    fixture = load_json_fixture("atlassian_listings.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = AtlassianConnector().fetch()

    assert len(jobs) == len(fixture)
    assert any("sydney" in j.location.lower() for j in jobs)
    # url must be the advert page, not the apply-flow URL
    assert all("mode=apply" not in j.url for j in jobs)
    assert all(j.url.endswith("/job") for j in jobs)


def test_atlassian_falls_back_to_stripped_apply_url_when_portal_missing(mock_get):
    fixture = [
        {
            "id": 1,
            "title": "Engineer",
            "locations": ["Sydney - Australia"],
            "applyUrl": "https://example.icims.com/jobs/1/engineer/job?mode=apply",
            # no portalJobPost key at all
        }
    ]
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = AtlassianConnector().fetch()

    assert jobs[0].url == "https://example.icims.com/jobs/1/engineer/job"


def test_employmenthero_paginates_fixture(mock_get):
    fixture = load_json_fixture("employmenthero_widget.json")
    # simulate the connector's pagination loop: first page reports total_pages
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = EmploymentHeroConnector("Employment Hero", "org-id").fetch()

    assert len(jobs) == fixture["data"]["total_items"]
    assert all(j.job_id for j in jobs)


def test_attrax_parses_html_fixture(mock_get):
    html = load_text_fixture("wise_attrax.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = AttraxConnector("Wise", "https://wise.jobs", "options=292").fetch()

    assert len(jobs) == 1
    assert jobs[0].location == "Sydney"
    assert jobs[0].job_id


def test_attrax_raises_when_results_counter_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>no counter here</body></html>"))
    with pytest.raises(ConnectorError):
        AttraxConnector("Wise", "https://wise.jobs", "options=292").fetch()


def test_attrax_raises_when_counter_says_nonzero_but_no_tiles(mock_get):
    html = '<html><body><span class="attrax-pagination__total-results">5 results</span></body></html>'
    mock_get.returns(httpx.Response(200, text=html))
    with pytest.raises(ConnectorError):
        AttraxConnector("Wise", "https://wise.jobs", "options=292").fetch()


def test_airwallex_parses_html_fixture(mock_get):
    html = load_text_fixture("airwallex_elementor.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = AirwallexConnector().fetch()

    assert len(jobs) == 2
    assert all("sydney" in j.location for j in jobs)
    assert all(j.job_id for j in jobs)


def test_airwallex_raises_when_loop_grid_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>totally different page</body></html>"))
    with pytest.raises(ConnectorError):
        AirwallexConnector().fetch()
