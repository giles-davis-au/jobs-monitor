import httpx
import pytest

from jobsmonitor.connectors.base import ConnectorError
from jobsmonitor.connectors.breezy import BreezyConnector
from tests.conftest import load_json_fixture


def test_breezy_parses_fixture(mock_get):
    fixture = load_json_fixture("breezy_stake.json")
    mock_get.returns(httpx.Response(200, json=fixture))

    jobs = BreezyConnector("Stake", "stake").fetch()

    assert len(jobs) == len(fixture)
    assert any("sydney" in j.location.lower() for j in jobs)
    assert all(j.url.startswith("https://stake.breezy.hr/") for j in jobs)


def test_breezy_raises_on_unexpected_shape(mock_get):
    mock_get.returns(httpx.Response(200, json={"not": "a list"}))
    with pytest.raises(ConnectorError):
        BreezyConnector("Stake", "stake").fetch()


def test_breezy_raises_on_network_error(mock_get):
    mock_get.raises(httpx.ConnectError("boom"))
    with pytest.raises(ConnectorError):
        BreezyConnector("Stake", "stake").fetch()
