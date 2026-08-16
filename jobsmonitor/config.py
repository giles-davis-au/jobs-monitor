from pathlib import Path

import yaml

from jobsmonitor.connectors.airwallex import AirwallexConnector
from jobsmonitor.connectors.ashby import AshbyConnector
from jobsmonitor.connectors.atlassian import AtlassianConnector
from jobsmonitor.connectors.attrax import AttraxConnector
from jobsmonitor.connectors.base import Connector
from jobsmonitor.connectors.employmenthero import EmploymentHeroConnector
from jobsmonitor.connectors.greenhouse import GreenhouseConnector
from jobsmonitor.connectors.lever import LeverConnector
from jobsmonitor.connectors.workable import WorkableConnector

CONNECTOR_REGISTRY = {
    "greenhouse": GreenhouseConnector,
    "lever": LeverConnector,
    "ashby": AshbyConnector,
    "workable": WorkableConnector,
    "atlassian": AtlassianConnector,
    "employmenthero": EmploymentHeroConnector,
    "attrax": AttraxConnector,
    "airwallex": AirwallexConnector,
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


def load_keywords(path: str | Path) -> list[str]:
    with open(path) as f:
        data = yaml.safe_load(f) or []

    if not isinstance(data, list) or not all(isinstance(p, str) for p in data):
        raise ValueError("keywords.yml must be a YAML list of phrase strings")

    return data
