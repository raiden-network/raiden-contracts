from typing import Optional

from semver import compare


def contracts_version_expects_deposit_limits(contracts_version: Optional[str]) -> bool:
    """ Answers whether TokenNetworkRegistry of the contracts_vesion needs deposit limits """
    if contracts_version is None:
        # contracts_version == None means the stock version in development.
        return True
    if contracts_version == "0.3._":
        return False
    return compare(contracts_version, "0.9.0") > -1


def contract_version_with_max_token_networks(version: Optional[str]) -> bool:
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
