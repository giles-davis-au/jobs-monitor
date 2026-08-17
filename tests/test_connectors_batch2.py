import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.employmenthero_marketplace import EmploymentHeroMarketplaceConnector
from jobsmonitor.connectors.teamtailor import TeamtailorConnector
from jobsmonitor.connectors.workday import WorkdayConnector
from tests.conftest import load_json_fixture, load_text_fixture


def test_workday_parses_fixture(mock_post):
    fixture = load_json_fixture("workday_lexisnexis.json")
    mock_post.returns(httpx.Response(200, json=fixture))

    jobs = WorkdayConnector("LexisNexis", "relx", "wd3", "LexisNexisLegal").fetch()

    assert len(jobs) == len(fixture["jobPostings"])
    assert all(j.url.startswith("https://relx.wd3.myworkdayjobs.com/LexisNexisLegal") for j in jobs)


def test_workday_stops_pagination_on_short_page_even_if_total_field_lies(mock_post):
    # Reproduces the real API quirk found during development: only the first
    # page reports an accurate `total`; later pages report total=0.
    page1 = {
        "total": 45,
        "jobPostings": [{"title": f"Job {i}", "externalPath": f"/job/{i}", "locationsText": "Sydney"} for i in range(20)],
    }
    page2 = {
        "total": 0,
        "jobPostings": [{"title": f"Job {i}", "externalPath": f"/job/{i}", "locationsText": "Sydney"} for i in range(20, 25)],
    }
    mock_post.returns(httpx.Response(200, json=page1))
    mock_post.returns(httpx.Response(200, json=page2))

    jobs = WorkdayConnector("Acme", "acme", "wd1", "Careers").fetch()

    assert len(jobs) == 25  # stopped after page2 returned fewer than a full page
    assert len(mock_post.calls) == 2


def test_workday_raises_on_unexpected_shape(mock_post):
    mock_post.returns(httpx.Response(200, json={"nope": "wrong shape"}))
    with pytest.raises(ConnectorError):
        WorkdayConnector("Acme", "acme", "wd1", "Careers").fetch()


def test_teamtailor_parses_fixture(mock_get):
    html = load_text_fixture("teamtailor_tyro.html")
    # fixture heading says "22 jobs" but only has 2 trimmed items — force
    # single-page termination by using an html string with a matching count instead
    html_single_page = html.replace("22 jobs", "2 jobs")
    mock_get.returns(httpx.Response(200, text=html_single_page))

    jobs = TeamtailorConnector("Tyro", "https://careers.tyro.com").fetch()

    assert len(jobs) == 2
    assert all(j.job_id for j in jobs)
    assert all(j.url.startswith("https://careers.tyro.com") for j in jobs)


def test_teamtailor_paginates_when_total_exceeds_one_page(mock_get):
    page1_html = """
    <html><body><h2>3 jobs</h2>
    <ul id="jobs_list_container">
      <li><a href="https://x/jobs/1-a">A</a><div class="mt-1 text-md"><span>Sydney</span></div></li>
      <li><a href="https://x/jobs/2-b">B</a><div class="mt-1 text-md"><span>Sydney</span></div></li>
    </ul></body></html>
    """
    page2_html = """
    <html><body><h2>3 jobs</h2>
    <ul id="jobs_list_container">
      <li><a href="https://x/jobs/3-c">C</a><div class="mt-1 text-md"><span>Sydney</span></div></li>
    </ul></body></html>
    """
    mock_get.returns(httpx.Response(200, text=page1_html))
    mock_get.returns(httpx.Response(200, text=page2_html))

    jobs = TeamtailorConnector("Acme", "https://x").fetch()

    assert len(jobs) == 3
    assert len(mock_get.calls) == 2


def test_teamtailor_raises_when_heading_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>no heading here</body></html>"))
    with pytest.raises(ConnectorError):
        TeamtailorConnector("Tyro", "https://careers.tyro.com").fetch()


def test_employmenthero_marketplace_parses_fixture(mock_get):
    html = load_text_fixture("employmenthero_marketplace_smokeball.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = EmploymentHeroMarketplaceConnector("Smokeball", "smokeball-australia-8gtiq").fetch()

    assert len(jobs) == 3
    assert all("sydney" in j.location.lower() for j in jobs)
    assert all(j.url.startswith("https://employmenthero.com") for j in jobs)


def test_employmenthero_marketplace_raises_when_container_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>no container</body></html>"))
    with pytest.raises(ConnectorError):
        EmploymentHeroMarketplaceConnector("Smokeball", "smokeball-australia-8gtiq").fetch()
