from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Job:
    """A single job posting exactly as a connector fetched it.

    `location` is whatever raw location text the source gives us (e.g.
    "Sydney, Australia", "Australia", "Remote - Remote"). Connectors do not
    interpret it — matcher.py decides Sydney-relevance from this text.
    """

    company: str
    job_id: str
    title: str
    url: str
    location: str


class LocationConfidence(str, Enum):
    CITY = "city"  # location text names Sydney specifically
    COUNTRY_ONLY = "country_only"  # site only exposes country-level location
