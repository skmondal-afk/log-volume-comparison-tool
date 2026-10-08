"""
dashboard_url.py

Parses a Grafana "BitC Blaze Log Dashboard" URL into the handful of
values that vary per-environment: time range, environment, servicename,
Loki datasource uid, and org id. Everything else (Loki host, app name,
components, log levels, threshold, ...) comes from config.py and is
shared across both URLs being compared.
"""

from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs


@dataclass
class UrlConfig:
    label: str  # "test1" / "test2" -- used in filenames and report headers
    raw_url: str
    org_id: str
    environment: str
    servicename: str
    start_time: str
    end_time: str
    datasource_uid: str

    @property
    def is_prod(self) -> bool:
        return self.environment.strip().lower() == "prod"


def _first(params: dict, key: str, default=None):
    values = params.get(key)
    return values[0] if values else default


def parse_dashboard_url(url: str, label: str) -> UrlConfig:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    org_id = _first(params, "orgId", "1")
    environment = _first(params, "var-blaze_environment")
    servicename = _first(params, "var-blaze_servicename")
    start_time = _first(params, "from")
    end_time = _first(params, "to")
    datasource_uid = _first(params, "var-loki_datasource")

    missing = [
        name
        for name, value in (
            ("var-blaze_environment", environment),
            ("var-blaze_servicename", servicename),
            ("from", start_time),
            ("to", end_time),
            ("var-loki_datasource", datasource_uid),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            f"Dashboard URL for {label} is missing required query param(s): "
            f"{', '.join(missing)}"
        )

    return UrlConfig(
        label=label,
        raw_url=url,
        org_id=org_id,
        environment=environment,
        servicename=servicename,
        start_time=start_time,
        end_time=end_time,
        datasource_uid=datasource_uid,
    )


def determine_scenario(url1_cfg: UrlConfig, url2_cfg: UrlConfig) -> str:
    """Returns "prod_vs_lt" if exactly one side is prod, else "same_type"."""
    return "prod_vs_lt" if url1_cfg.is_prod != url2_cfg.is_prod else "same_type"


def assign_labels(url1_cfg: UrlConfig, url2_cfg) -> None:
    """
    Derives report/filename labels from each URL's environment: if both
    environments are the same (e.g. "test" vs "test"), labels become
    "test1"/"test2"; if they differ (e.g. "test" vs "prod"), labels are
    just the raw environment names since they're already distinguishable.
    Mutates url1_cfg.label (and url2_cfg.label, if given) in place.
    """
    if not url2_cfg:
        url1_cfg.label = url1_cfg.environment
        return

    if url1_cfg.environment == url2_cfg.environment:
        url1_cfg.label = f"{url1_cfg.environment}1"
        url2_cfg.label = f"{url2_cfg.environment}2"
    else:
        url1_cfg.label = url1_cfg.environment
        url2_cfg.label = url2_cfg.environment
