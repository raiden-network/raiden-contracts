from enum import Enum
from typing import Optional

from semantic_version import SimpleSpec, Version


class ContractFeature(Enum):
    SERVICES = "services"
    MAX_TOKEN_NETWORKS = "max_token_networks"
    INITIAL_SERVICE_DEPOSIT = "initial_service_deposit"
    MS_NEEDS_TOKENNETWORK_REGISTRY = "ms_needs_tokennetwork_registry"


CONTRACT_FEATURE_VERSIONS = {
    ContractFeature.SERVICES: SimpleSpec(">=0.8.0"),
    ContractFeature.MAX_TOKEN_NETWORKS: SimpleSpec(">=0.9.0"),
    ContractFeature.INITIAL_SERVICE_DEPOSIT: SimpleSpec(">=0.18.0"),
    ContractFeature.MS_NEEDS_TOKENNETWORK_REGISTRY: SimpleSpec(">=0.22.0"),
}


def _matches_feature(feature: ContractFeature, version: Optional[str]) -> bool:
    """Returns a bool indicating whether the passed version matches the minimum required
    version for the given feature."""

    if version is None:
        # contracts_version == None means the stock version in development.
        return True
    return CONTRACT_FEATURE_VERSIONS[feature].match(Version(version))


def contracts_version_with_max_token_networks(version: Optional[str]) -> bool:
    return _matches_feature(ContractFeature.MAX_TOKEN_NETWORKS, version)


def contracts_version_provides_services(version: Optional[str]) -> bool:
    return _matches_feature(ContractFeature.SERVICES, version)


def contracts_version_has_initial_service_deposit(version: Optional[str]) -> bool:
    return _matches_feature(ContractFeature.INITIAL_SERVICE_DEPOSIT, version)


def contracts_version_monitoring_service_takes_token_network_registry(
    version: Optional[str],
) -> bool:
    return _matches_feature(ContractFeature.MS_NEEDS_TOKENNETWORK_REGISTRY, version)
