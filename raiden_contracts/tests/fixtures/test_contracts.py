import pytest

from raiden_contracts.constants import TEST_SETTLE_TIMEOUT_MAX, TEST_SETTLE_TIMEOUT_MIN


@pytest.fixture()
def token_network_test_storage(
    deploy_tester_contract, web3, custom_token, secret_registry_contract
):
    return deploy_tester_contract(
        "TokenNetworkInternalStorageTest",
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )


@pytest.fixture()
def token_network_test_signatures(
    deploy_tester_contract, web3, custom_token, secret_registry_contract
):
    return deploy_tester_contract(
        "TokenNetworkSignatureTest",
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )


@pytest.fixture()
def token_network_test_utils(deploy_tester_contract, web3, custom_token, secret_registry_contract):
    return deploy_tester_contract(
        "TokenNetworkUtilsTest",
        [
            custom_token.address,
            secret_registry_contract.address,
            int(web3.version.network),
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
        ],
    )
