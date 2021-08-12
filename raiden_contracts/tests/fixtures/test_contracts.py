from typing import Callable

import pytest
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MAX, TEST_SETTLE_TIMEOUT_MIN


@pytest.fixture
def token_network_test_storage(
    deploy_tester_contract: Callable,
    web3: Web3,
    custom_token: Contract,
    secret_registry_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "TokenNetworkInternalStorageTest",
        [
            custom_token.address,
            secret_registry_contract.address,
            web3.eth.chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )


@pytest.fixture
def token_network_test_signatures(
    deploy_tester_contract: Callable,
    custom_token: Contract,
    secret_registry_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "TokenNetworkSignatureTest",
        _token_address=custom_token.address,
        _secret_registry=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
    )


@pytest.fixture
def token_network_test_utils(
    deploy_tester_contract: Callable,
    custom_token: Contract,
    secret_registry_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "TokenNetworkUtilsTest",
        _token_address=custom_token.address,
        _secret_registry=secret_registry_contract.address,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
    )


@pytest.fixture
def signature_test_contract(deploy_tester_contract: Callable) -> Contract:
    return deploy_tester_contract("SignatureVerifyTest")
