from jobsmonitor.connectors.tiktok import TikTokConnector


def test_parse_card_splits_title_and_folds_remaining_lines_into_location():
    connector = TikTokConnector()
    card = {
        "href": "https://lifeattiktok.com/search/7615005577716730117",
        "text": "Frontend Engineer Graduate, TikTok LIVE (Sydney) - 2027 Start (BS/MS)\nSydney\nTechnology - Frontend\nRegular",
    }

    job = connector._parse_card(card)

    assert job.company == "TikTok"
    assert job.job_id == "7615005577716730117"
    assert job.title == "Frontend Engineer Graduate, TikTok LIVE (Sydney) - 2027 Start (BS/MS)"
    assert job.location == "Sydney; Technology - Frontend; Regular"
    assert job.url == card["href"]


def test_parse_card_handles_minimal_text():
    connector = TikTokConnector()
    card = {"href": "https://lifeattiktok.com/search/123", "text": "Some Role\nSydney"}

    job = connector._parse_card(card)

    assert job.title == "Some Role"
    assert job.location == "Sydney"
    assert job.job_id == "123"
