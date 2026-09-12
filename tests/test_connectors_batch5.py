import httpx
import pytest
from bs4 import BeautifulSoup

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.elmo import ElmoConnector
from jobsmonitor.connectors.livehire import LiveHireConnector
from tests.conftest import load_json_fixture, load_text_fixture


def test_elmo_parse_card_extracts_title_url_location():
    html = load_text_fixture("elmo_automic.html")
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("#section-list ul.list-group li.list-group-item")
    connector = ElmoConnector("Automic Group", "automicgroup")

    jobs = [connector._parse_card(c, "https://automicgroup.elmotalent.com.au") for c in cards]

    assert len(jobs) == 2
    assert jobs[0].title == "Manager/ Senior Manager - Employee Share Plans - Sydney/ Perth/ Melbourne"
    assert jobs[0].url == "https://automicgroup.elmotalent.com.au/careers/default/job/view/375"
    assert jobs[0].location == "Sydney"
    assert jobs[1].job_id == "/careers/default/job/view/381"


def test_elmo_parse_card_handles_missing_location_icon():
    html = "<li class='list-group-item'><a class='redirect_elmo_link' href='/careers/default/job/view/1'>Role</a></li>"
    soup = BeautifulSoup(html, "html.parser")
    card = soup.select_one("li")
    connector = ElmoConnector("Automic Group", "automicgroup")

    job = connector._parse_card(card, "https://automicgroup.elmotalent.com.au")

    assert job.title == "Role"
    assert job.location == ""


def test_livehire_parses_fixture(mock_get, mock_post):
    mock_get.returns(httpx.Response(200, json={"access_token": "fake-token", "token_type": "Bearer"}))
    fixture = load_json_fixture("livehire_ooh.json")
    mock_post.returns(httpx.Response(200, json=fixture))

    jobs = LiveHireConnector("oOh!media", "ooh").fetch()

    assert len(jobs) == 2
    assert jobs[0].title == "Campaign Delivery Executive"
    assert jobs[0].location == "Melbourne VIC, Australia"
    assert jobs[0].url == (
        "https://www.livehire.com/careers/ooh/job/PBFPY/BM0Q02FYJT/campaign-delivery-executive"
    )
    assert jobs[0].job_id == "BM0Q02FYJT"


def test_livehire_paginates_until_short_page(mock_get, mock_post):
    mock_get.returns(httpx.Response(200, json={"access_token": "fake-token"}))
    page1 = {"jobs": [{"advertUrlCode": str(i), "roleName": f"Job {i}", "urlCode": str(i), "seoSlug": "job"} for i in range(20)]}
    page2 = {"jobs": [{"advertUrlCode": "20", "roleName": "Job 20", "urlCode": "20", "seoSlug": "job"}]}
    mock_post.returns(httpx.Response(200, json=page1))
    mock_post.returns(httpx.Response(200, json=page2))

    jobs = LiveHireConnector("oOh!media", "ooh").fetch()

    assert len(jobs) == 21
    assert len(mock_post.calls) == 2


def test_livehire_raises_on_token_failure(mock_get):
    mock_get.raises(httpx.ConnectError("boom"))
    with pytest.raises(ConnectorError):
        LiveHireConnector("oOh!media", "ooh").fetch()
