from pathlib import Path

import yaml

from jobsmonitor.connectors.airwallex import AirwallexConnector
from jobsmonitor.connectors.ashby import AshbyConnector
from jobsmonitor.connectors.atlassian import AtlassianConnector
from jobsmonitor.connectors.attrax import AttraxConnector
from jobsmonitor.connectors.base import Connector
from jobsmonitor.connectors.breezy import BreezyConnector
from jobsmonitor.connectors.canva import CanvaConnector
from jobsmonitor.connectors.employmenthero import EmploymentHeroConnector
from jobsmonitor.connectors.employmenthero_marketplace import EmploymentHeroMarketplaceConnector
from jobsmonitor.connectors.eightfold import EightfoldConnector
from jobsmonitor.connectors.greenhouse import GreenhouseConnector
from jobsmonitor.connectors.lever import LeverConnector
from jobsmonitor.connectors.teamtailor import TeamtailorConnector
from jobsmonitor.connectors.tiktok import TikTokConnector
from jobsmonitor.connectors.uber import UberConnector
from jobsmonitor.connectors.workable import WorkableConnector
from jobsmonitor.connectors.workday import WorkdayConnector
from jobsmonitor.connectors.zip import ZipConnector

CONNECTOR_REGISTRY = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
    "workable": WorkableConnector,
    "atlassian": AtlassianConnector,
    "employmenthero": EmploymentHeroConnector,
    "attrax": AttraxConnector,
    "airwallex": AirwallexConnector,
    "canva": CanvaConnector,
    "workday": WorkdayConnector,
    "teamtailor": TeamtailorConnector,
    "employmenthero_marketplace": EmploymentHeroMarketplaceConnector,
    "uber": UberConnector,
    "eightfold": EightfoldConnector,
    "zip": ZipConnector,
    "tiktok": TikTokConnector,
    "breezy": BreezyConnector,
}


def load_companies(path: str | Path) -> list[Connector]:
    with open(path) as f:
        raw = yaml.safe_load(f) or []

    connectors = []
    for entry in raw:
        name = entry["name"]
        conn_type = entry["connector"]
        config = entry.get("config", {})

        cls = CONNECTOR_REGISTRY.get(conn_type)
        if cls is None:
            raise ValueError(
                f"companies.yml: unknown connector type '{conn_type}' for company '{name}' "
                f"(known types: {', '.join(sorted(CONNECTOR_REGISTRY))})"
            )
        connectors.append(cls(company=name, **config))

    return connectors


def load_company_homepages(path: str | Path) -> dict[str, str]:
    """company name -> public homepage URL, for the GSheet log's Company
    hyperlink. Entries with no `homepage` set are simply omitted.
    """
    with open(path) as f:
        raw = yaml.safe_load(f) or []

    return {entry["name"]: entry["homepage"] for entry in raw if entry.get("homepage")}


def load_keywords(path: str | Path) -> list[str]:
    with open(path) as f:
        data = yaml.safe_load(f) or []

    if not isinstance(data, list) or not all(isinstance(p, str) for p in data):
        raise ValueError("keywords.yml must be a YAML list of phrase strings")

    return data
