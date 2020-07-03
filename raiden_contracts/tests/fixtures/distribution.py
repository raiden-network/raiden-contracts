from typing import Callable, Dict

import pytest
from eth_typing import HexAddress
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_DISTRIBUTION
from raiden_contracts.utils.proofs import sign_claim


@pytest.fixture()
def get_distribution(deploy_tester_contract: Callable) -> Callable:
    def get(**arguments: Dict) -> Contract:
        return deploy_tester_contract(CONTRACT_DISTRIBUTION, **arguments)

    return get


@pytest.fixture(scope="session")
def distribution_constructor_args(web3: Web3, custom_token: Contract) -> Dict:
    return {
        "_token_address": custom_token.address,
        "_chain_id": web3.eth.chainId,
    }


@pytest.fixture(scope="session")
def distribution_contract(
    deploy_tester_contract: Callable, distribution_constructor_args: Dict
) -> Contract:
    """Deployed TokenNetworkRegistry contract"""
    return deploy_tester_contract(CONTRACT_DISTRIBUTION, **distribution_constructor_args)


@pytest.fixture
def token_network_registry_address(distribution_contract: Contract) -> HexAddress:
    """Address of TokenNetworkRegistry contract"""
    return distribution_contract.address


@pytest.fixture
def make_claim(web3: Web3, distribution_contract: Contract, get_private_key: Callable) -> Callable:
    chain_id = web3.eth.chainId

    def f(
        owner: HexAddress,
        partner: HexAddress,
        total_amount: int = 10,
        chain_id: int = chain_id,
        distribution_address: HexAddress = distribution_contract.address,
    ) -> dict:
        iou = dict(
            owner=owner,
            partner=partner,
            total_amount=total_amount,
            chain_id=chain_id,
            distribution_address=distribution_address,
        )
        iou["signature"] = sign_claim(get_private_key(owner), **iou)  # type: ignore
        del iou["chain_id"]
        del iou["distribution_address"]
        return iou

    return f
