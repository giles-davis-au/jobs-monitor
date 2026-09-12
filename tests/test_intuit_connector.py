import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.intuit import IntuitConnector
from tests.conftest import load_text_fixture


def test_intuit_parses_fixture_without_needing_pagination(mock_get):
    html = load_text_fixture("intuit_talentbrew.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = IntuitConnector("Intuit", "sydney-jobs", "2077456-2155400-2147714", "4").fetch()

    assert len(jobs) == 2
    assert jobs[0].title == "Strategic Money Specialist"
    assert jobs[0].location == "Multiple Locations"
    assert jobs[0].url == (
        "https://jobs.intuit.com/job/atlanta/strategic-money-specialist/27595/100371537856"
    )
    assert jobs[0].job_id == "23849"


def test_intuit_genuinely_zero_jobs_is_empty_not_an_error(mock_get):
    html = (
        '<html><body><section id="search-results" data-total-job-results="0">'
        '<section id="search-results-list"><p id="no-results">no jobs</p></section>'
        "</section></body></html>"
    )
    mock_get.returns(httpx.Response(200, text=html))

    jobs = IntuitConnector("Intuit", "sydney-jobs", "2077456-2155400-2147714", "4").fetch()

    assert jobs == []


def test_intuit_paginates_when_total_exceeds_first_page(mock_get):
    html = load_text_fixture("intuit_talentbrew.html").replace(
        'data-total-job-results="2"', 'data-total-job-results="3"'
    )
    mock_get.returns(httpx.Response(200, text=html))
    page2_fragment = (
        '<ul class="search-list"><li data-intuit-jobid="999">'
        '<a class="sr-item" href="/job/x/role/27595/999" data-title="Role">'
        "<h2>Role</h2><span class=\"job-location\">Sydney</span></a></li></ul>"
    )
    mock_get.returns(httpx.Response(200, json={"results": page2_fragment, "hasContent": True}))

    jobs = IntuitConnector("Intuit", "sydney-jobs", "2077456-2155400-2147714", "4").fetch()

    assert len(jobs) == 3
    assert jobs[2].job_id == "999"
    assert len(mock_get.calls) == 2


def test_intuit_raises_when_total_count_attribute_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>no results section here</body></html>"))
    with pytest.raises(ConnectorError):
        IntuitConnector("Intuit", "sydney-jobs", "2077456-2155400-2147714", "4").fetch()
