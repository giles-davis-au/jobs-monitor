import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.eightfold import EightfoldConnector
from jobsmonitor.connectors.zip import ZipConnector
from tests.conftest import load_json_fixture, load_text_fixture


def test_eightfold_parses_pcsx_variant(mock_get):
    fixture = load_json_fixture("eightfold_pcsx_paypal.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = EightfoldConnector("PayPal", "https://paypal.eightfold.ai/api/pcsx/search", "paypal.com").fetch()

    assert len(jobs) == len(fixture["data"]["positions"])
    assert all(j.url.startswith("https://paypal.eightfold.ai/careers/job/") for j in jobs)


def test_eightfold_parses_applyv2_variant(mock_get):
    fixture = load_json_fixture("eightfold_applyv2_costar.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = EightfoldConnector("Domain", "https://careers.costargroup.com/api/apply/v2/jobs", "costar.com").fetch()

    assert len(jobs) == len(fixture["positions"])
    assert all(j.url.startswith("https://careers.costargroup.com") or "eightfold.ai" in j.url for j in jobs)


def test_eightfold_paginates_via_start_offset(mock_get):
    page1 = {"data": {"positions": [{"id": i, "name": f"Job {i}", "locations": [], "positionUrl": f"/j/{i}"} for i in range(4)], "count": 6}}
    page2 = {"data": {"positions": [{"id": i, "name": f"Job {i}", "locations": [], "positionUrl": f"/j/{i}"} for i in range(4, 6)], "count": 6}}
    mock_get.returns(httpx.Response(200, json=page1))
    mock_get.returns(httpx.Response(200, json=page2))

    jobs = EightfoldConnector("Acme", "https://acme.eightfold.ai/api/pcsx/search", "acme.com").fetch()

    assert len(jobs) == 6
    assert len(mock_get.calls) == 2


def test_eightfold_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"nope": "wrong"}))
    with pytest.raises(ConnectorError):
        EightfoldConnector("Acme", "https://acme.eightfold.ai/api/pcsx/search", "acme.com").fetch()


def test_zip_parses_fixture(mock_get):
    html = load_text_fixture("zip_roles.html")
    mock_get.returns(httpx.Response(200, text=html))

    jobs = ZipConnector().fetch()

    assert len(jobs) == 3
    assert all(j.url.startswith("https://zip.co/careers/roles/") for j in jobs)
    assert all(j.title for j in jobs)


def test_zip_raises_when_total_present_but_no_links(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body><p>5 roles in 1 location</p></body></html>"))
    with pytest.raises(ConnectorError):
        ZipConnector().fetch()


def test_zip_raises_when_roles_count_missing(mock_get):
    mock_get.returns(httpx.Response(200, text="<html><body>nothing here</body></html>"))
    with pytest.raises(ConnectorError):
        ZipConnector().fetch()
