from typing import Optional

from semver import compare

from raiden_contracts.constants import CONTRACT_TOKEN_NETWORK_REGISTRY
from raiden_contracts.contract_manager import ContractManager, contracts_precompiled_path


def contracts_version_expects_deposit_limits(contracts_version: Optional[str]) -> bool:
    """ Answers whether TokenNetworkRegistry of the contracts_vesion needs deposit limits """
    if contracts_version is None:
        return True
    if contracts_version == "0.3._":
        return False
    return compare(contracts_version, "0.9.0") > -1


def contract_version_with_max_token_networks(version: Optional[str]) -> bool:
    manager = ContractManager(contracts_precompiled_path(version))
    abi = manager.get_contract_abi(CONTRACT_TOKEN_NETWORK_REGISTRY)
    constructors = list(filter(lambda x: x["type"] == "constructor", abi))
    assert len(constructors) == 1
    inputs = constructors[0]["inputs"]
    max_token_networks_args = list(filter(lambda x: x["name"] == "_max_token_networks", inputs))
    found_args = len(max_token_networks_args)
    if found_args == 0:
        return False
    elif found_args == 1:
        return True
    else:
        raise ValueError(
            "TokenNetworkRegistry's constructor has more than one arguments that are "
            'called "_max_token_networks".'
        )
