from jobsmonitor.models import Job, LocationConfidence

# Other major AU cities: if one of these is named and Sydney isn't, we know
# the role is NOT Sydney and should be excluded outright — not flagged as
# ambiguous just because "Australia" also appears in the same text (e.g.
# "Melbourne, Australia").
OTHER_AU_CITIES = {
    "melbourne",
    "brisbane",
    "perth",
    "adelaide",
    "canberra",
    "hobart",
    "darwin",
    "gold coast",
    "newcastle",
    "wollongong",
    "geelong",
}

# Company office suburbs within Greater Sydney that don't contain the word
# "Sydney" at all (e.g. Domain's HQ is listed as "Pyrmont, New South Wales,
# Australia" with no "Sydney" anywhere in the string — confirmed missing 31
# real postings before this list was added). This is inherently a partial,
# maintained-by-hand list of common tech/corporate-office suburbs, not
# exhaustive of all ~600 Greater Sydney suburbs — a company in an unlisted
# suburb will still be missed. Extend this list if that happens.
SYDNEY_SUBURBS = {
    "pyrmont",
    "north sydney",
    "st leonards",
    "barangaroo",
    "ultimo",
    "surry hills",
    "chatswood",
    "parramatta",
    "macquarie park",
    "redfern",
    "alexandria",
    "zetland",
    "waterloo",
    "haymarket",
    "the rocks",
    "circular quay",
    "milsons point",
    "north ryde",
    "rhodes",
    "docklands nsw",
    "barangaroo south",
}


def classify_location(location_text: str) -> LocationConfidence | None:
    """Decide whether a job's raw location text is Sydney-relevant.

    Returns CITY when the text names Sydney specifically (including known
    Sydney-metro suburbs that don't literally say "Sydney" — see
    SYDNEY_SUBURBS), COUNTRY_ONLY when it only narrows down to Australia
    with no specific city (some sites — e.g. Deputy, Atlassian — don't
    always give one), or None when it names a different Australian city or
    isn't Australia-relevant at all (exclude).
    """
    text = location_text.lower()
    if "sydney" in text or any(suburb in text for suburb in SYDNEY_SUBURBS):
        return LocationConfidence.CITY
    if any(city in text for city in OTHER_AU_CITIES):
        return None
    if "australia" in text:
        return LocationConfidence.COUNTRY_ONLY
    return None


def matches_keywords(title: str, keyword_phrases: list[str]) -> bool:
    """True if the title contains any keyword phrase as a whole, case-insensitive
    substring — never split into individual words. "Program Manager" matches
    "Senior Program Manager, Platform" but not "Engineering Manager".
    """
    title_lower = title.lower()
    return any(phrase.lower() in title_lower for phrase in keyword_phrases)


def find_matches(
    jobs: list[Job], keyword_phrases: list[str]
) -> list[tuple[Job, LocationConfidence]]:
    """Jobs that are both Sydney-relevant and keyword-matched, paired with
    how confident we are about the location (for flagging country-only hits
    in the digest rather than silently dropping or silently trusting them).
    """
    matches = []
    for job in jobs:
        confidence = classify_location(job.location)
        if confidence is None:
            continue
        if matches_keywords(job.title, keyword_phrases):
            matches.append((job, confidence))
    return matches
