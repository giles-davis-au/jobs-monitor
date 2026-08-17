from jobsmonitor.connectors.uber import UberConnector
from tests.conftest import load_json_fixture


def test_parse_job_builds_absolute_url_and_joined_locations():
    connector = UberConnector()
    fixture = load_json_fixture("uber_jobs.json")
    raw = fixture["jobs"][0]

    job = connector._parse_job(raw)

    assert job.company == "Uber"
    assert job.job_id == "301367"
    assert job.title == "Tech People Partner"
    assert job.url == "https://www.uber.com/en/jobs/301367/"
    assert job.location == "San Francisco, California, United States"


def test_parse_job_joins_multiple_locations():
    connector = UberConnector()
    fixture = load_json_fixture("uber_jobs.json")
    multi_location_job = next(j for j in fixture["jobs"] if len(j["Locations"]) > 1)

    job = connector._parse_job(multi_location_job)

    assert "; " in job.location
    assert job.location.count(";") == len(multi_location_job["Locations"]) - 1


def test_parse_job_finds_sydney_in_location_text():
    connector = UberConnector()
    raw = {
        "Id": "999",
        "Title": "Strategy Manager",
        "Locations": [{"City": "Sydney", "Region": "New South Wales", "Country": "Australia"}],
        "Urls": [{"Url": "/en/jobs/999/", "IsDefault": True}],
    }

    job = connector._parse_job(raw)

    assert "sydney" in job.location.lower()
