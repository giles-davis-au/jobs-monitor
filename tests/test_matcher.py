from jobsmonitor.matcher import classify_location, find_matches, matches_keywords
from jobsmonitor.models import Job, LocationConfidence


def test_classify_location_sydney():
    assert classify_location("Sydney, Australia") == LocationConfidence.CITY
    assert classify_location("Remote - APAC - Remote; Sydney - Australia") == LocationConfidence.CITY


def test_classify_location_other_au_city_excluded():
    assert classify_location("Melbourne, Australia") is None
    assert classify_location("Brisbane, Australia") is None


def test_classify_location_country_only():
    assert classify_location("Australia") == LocationConfidence.COUNTRY_ONLY


def test_classify_location_non_au_excluded():
    assert classify_location("Singapore") is None
    assert classify_location("Remote - Remote") is None


def test_matches_keywords_is_whole_phrase_not_word_level():
    assert matches_keywords("Senior Program Manager, Platform", ["Program Manager"]) is True
    assert matches_keywords("Engineering Manager", ["Program Manager"]) is False
    assert matches_keywords("Program Lead", ["Program Manager"]) is False


def test_matches_keywords_case_insensitive_and_any_phrase():
    assert matches_keywords("senior programme manager", ["Programme Manager"]) is True
    assert matches_keywords("Backend Engineer", ["Program Manager", "Senior Project Manager"]) is False


def test_find_matches_combines_keyword_and_location_filters():
    jobs = [
        Job("A", "1", "Senior Project Manager", "https://x/1", "Sydney, Australia"),
        Job("A", "2", "Senior Project Manager", "https://x/2", "Melbourne, Australia"),
        Job("A", "3", "Backend Engineer", "https://x/3", "Sydney, Australia"),
        Job("A", "4", "Program Manager", "https://x/4", "Australia"),
    ]
    matches = find_matches(jobs, ["Program Manager", "Senior Project Manager"])

    ids_and_confidence = {(job.job_id, conf) for job, conf in matches}
    assert ids_and_confidence == {
        ("1", LocationConfidence.CITY),
        ("4", LocationConfidence.COUNTRY_ONLY),
    }
