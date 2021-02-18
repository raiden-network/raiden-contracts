from typing import Optional

from semver import VersionInfo


def contracts_version_with_max_token_networks(version: Optional[str]) -> bool:
    if version is None:
        # contracts_version == None means the stock version in development.
        return True
    return VersionInfo.parse(version).compare("0.9.0") >= 0


def contracts_version_provides_services(version: Optional[str]) -> bool:
    if version is None:
        # contracts_version == None means the stock version in development.
        return True
    return VersionInfo.parse(version).compare("0.8.0") >= 0


def contracts_version_has_initial_service_deposit(version: Optional[str]) -> bool:
    if version is None:
        # contracts_versoin == None means the stock version in development.
        return True
    return VersionInfo.parse(version).compare("0.18.0") > 0


def contracts_version_monitoring_service_takes_token_network_registry(
    version: Optional[str],
) -> bool:
    """Returns true if the contracts_version's MonitoringService contracts

    expects a TokenNetworkRegistry address as a constructor argument.
    """
    if version is None:
        # stock version in `data`
        return True
    return VersionInfo.parse(version).compare("0.22.0") > 0
