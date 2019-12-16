from typing import Optional

from semver import compare


def contracts_version_with_max_token_networks(version: Optional[str]) -> bool:
    if version is None:
        # contracts_version == None means the stock version in development.
        return True
    if version == "0.3._":
        return False
    if version == "0.8.0_unlimited":
        return False
    return compare(version, "0.9.0") >= 0


def contracts_version_provides_services(version: Optional[str]) -> bool:
    if version is None:
        # contracts_version == None means the stock version in development.
        return True
    if version == "0.3._":
        return False
    if version == "0.8.0_unlimited":
        return True
    return compare(version, "0.8.0") >= 0


def contracts_version_has_initial_service_deposit(version: Optional[str]) -> bool:
    if version is None:
        # contracts_versoin == None means the stock version in development.
        return True
    if version == "0.3._":
        return False
    if version == "0.8.0_unlimited":
        return False
    return compare(version, "0.18.0") > 0


def contracts_version_monitoring_service_takes_token_network_registry(
    version: Optional[str],
) -> bool:
    """ Returns true if the contracts_version's MonitoringService contracts

    expects a TokenNetworkRegistry address as a constructor argument.
    """
    if version is None:
        # stock version in `data`
        return True
    if version == "0.3._":
        return False
    if version == "0.8.0_unlimited":
        return False
    return compare(version, "0.22.0") > 0
