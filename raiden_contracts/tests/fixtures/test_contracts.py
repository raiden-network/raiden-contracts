import pytest

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)


@pytest.fixture()
def token_network_test_storage(
        deploy_tester_contract,
        token_network_utils_library,
        web3,
        custom_token,
        secret_registry_contract,
):
    return deploy_tester_contract(
        'TokenNetworkInternalStorageTest',
        # {'TokenNetworkUtils': token_network_utils_library.address},
        {'/Users/loredana/ETH/raiden-contracts': token_network_utils_library.address},
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )[0]


@pytest.fixture()
def token_network_test_signatures(
        deploy_tester_contract,
        token_network_utils_library,
        web3,
        custom_token,
        secret_registry_contract,
):
    return deploy_tester_contract(
        'TokenNetworkSignatureTest',
        # {'TokenNetworkUtils': token_network_utils_library.address},
        {'/Users/loredana/ETH/raiden-contracts': token_network_utils_library.address},
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )[0]


@pytest.fixture()
def token_network_test_utils(
        deploy_tester_contract,
        token_network_utils_library,
        web3,
        custom_token,
        secret_registry_contract,
):
    return deploy_tester_contract(
        'TokenNetworkUtilsTest',
        # {'TokenNetworkUtils': token_network_utils_library.address},
        {'/Users/loredana/ETH/raiden-contracts': token_network_utils_library.address},
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )[0]


@pytest.fixture
def signature_test_contract(deploy_tester_contract, token_network_utils_library):
    return deploy_tester_contract(
        'SignatureVerifyTest',
        # {'TokenNetworkUtils': token_network_utils_library.address},
        {'/Users/loredana/ETH/raiden-contracts': token_network_utils_library.address},
        [],
    )[0]
