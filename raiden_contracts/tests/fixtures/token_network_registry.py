from typing import Callable, Dict

import pytest
from eth_typing import HexAddress
from eth_utils import is_address
from web3 import Web3
from web3.contract import Contract, get_event_data

from raiden_contracts.constants import (
    CONTRACT_TOKEN_NETWORK,
    CONTRACT_TOKEN_NETWORK_REGISTRY,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.contract_manager import ContractManager
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS
from raiden_contracts.utils.transaction import check_successful_tx


@pytest.fixture()
def get_token_network_registry(deploy_tester_contract: Callable) -> Callable:
    def get(**arguments: Dict) -> Contract:
        return deploy_tester_contract(CONTRACT_TOKEN_NETWORK_REGISTRY, **arguments)

    return get


@pytest.fixture(scope="session")
def token_network_registry_constructor_args(
    web3: Web3, secret_registry_contract: Contract
) -> Dict:
    return {
        "_secret_registry_address": secret_registry_contract.address,
        "_chain_id": web3.eth.chainId,
        "_settlement_timeout_min": TEST_SETTLE_TIMEOUT_MIN,
        "_settlement_timeout_max": TEST_SETTLE_TIMEOUT_MAX,
        "_max_token_networks": 1,
    }


@pytest.fixture(scope="session")
def token_network_registry_contract(
    deploy_tester_contract: Callable, token_network_registry_constructor_args: Dict
) -> Contract:
    """Deployed TokenNetworkRegistry contract"""
    return deploy_tester_contract(
        CONTRACT_TOKEN_NETWORK_REGISTRY, **token_network_registry_constructor_args
    )


@pytest.fixture(scope="session")
def token_network_registry_contract2(
    deploy_tester_contract: Callable, token_network_registry_constructor_args: Dict
) -> Contract:
    """Another deployed TokenNetworkRegistry contract

    to which service payment contracts should not collaborate."""
    return deploy_tester_contract(
        CONTRACT_TOKEN_NETWORK_REGISTRY, **token_network_registry_constructor_args
    )


@pytest.fixture
def token_network_registry_address(token_network_registry_contract: Contract) -> HexAddress:
    """Address of TokenNetworkRegistry contract"""
    return token_network_registry_contract.address


@pytest.fixture
def add_and_register_token(
    web3: Web3,
    token_network_registry_contract: Contract,
    deploy_token_contract: Callable,
    contracts_manager: ContractManager,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> Callable:
    """Deploy a token and register it in TokenNetworkRegistry"""

    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str) -> Contract:
        token_contract = deploy_token_contract(initial_amount, decimals, token_name, token_symbol)
        txid = call_and_transact(
            token_network_registry_contract.functions.createERC20TokenNetwork(
                token_contract.address,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ),
            {"from": DEPLOYER_ADDRESS},
        )
        (tx_receipt, _) = check_successful_tx(web3, txid)
        assert len(tx_receipt["logs"]) == 1
        event_abi = contracts_manager.get_event_abi(
            CONTRACT_TOKEN_NETWORK_REGISTRY, EVENT_TOKEN_NETWORK_CREATED
        )
        decoded_event = get_event_data(event_abi, tx_receipt["logs"][0])
        assert decoded_event is not None
        assert is_address(decoded_event["args"]["token_address"])
        assert is_address(decoded_event["args"]["token_network_address"])
        token_network_address = decoded_event["args"]["token_network_address"]
        token_network_abi = contracts_manager.get_contract_abi(CONTRACT_TOKEN_NETWORK)
        return web3.eth.contract(abi=token_network_abi, address=token_network_address)

    return f
