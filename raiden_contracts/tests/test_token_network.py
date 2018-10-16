import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.tests.utils import MAX_UINT256
from raiden_contracts.tests.fixtures.config import (
    EMPTY_ADDRESS,
    FAKE_ADDRESS,
)
from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)


def test_version(token_network):
    assert token_network.functions.contract_version().call() == CONTRACTS_VERSION


def test_constructor_call(
        web3,
        get_token_network,
        custom_token,
        secret_registry_contract,
        get_accounts,
):
    (A, deprecation_executor) = get_accounts(2)
    chain_id = int(web3.version.network)
    settle_min = TEST_SETTLE_TIMEOUT_MIN
    settle_max = TEST_SETTLE_TIMEOUT_MAX
    with pytest.raises(TypeError):
        get_token_network([])
    with pytest.raises(TypeError):
        get_token_network([
            3,
            secret_registry_contract.address,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            0,
            secret_registry_contract.address,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            '',
            secret_registry_contract.address,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            FAKE_ADDRESS,
            secret_registry_contract.address,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            3,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            0,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            '',
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            FAKE_ADDRESS,
            chain_id,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            '',
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            -3,
            settle_min,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            '',
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            -3,
            settle_max,
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            settle_min,
            '',
            deprecation_executor,
        ])
    with pytest.raises(TypeError):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            settle_min,
            -3,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            EMPTY_ADDRESS,
            secret_registry_contract.address,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])
    with pytest.raises(TransactionFailed):
        get_token_network([
            A,
            secret_registry_contract.address,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])
    with pytest.raises(TransactionFailed):
        get_token_network([
            secret_registry_contract.address,
            secret_registry_contract.address,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            EMPTY_ADDRESS,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])
    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            A,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            0,
            TEST_SETTLE_TIMEOUT_MIN,
            TEST_SETTLE_TIMEOUT_MAX,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            TEST_SETTLE_TIMEOUT_MAX,
            TEST_SETTLE_TIMEOUT_MIN,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            0,
            TEST_SETTLE_TIMEOUT_MIN,
            deprecation_executor,
        ])

    with pytest.raises(TransactionFailed):
        get_token_network([
            custom_token.address,
            secret_registry_contract.address,
            chain_id,
            TEST_SETTLE_TIMEOUT_MIN,
            0,
            deprecation_executor,
        ])

    get_token_network([
        custom_token.address,
        secret_registry_contract.address,
        chain_id,
        TEST_SETTLE_TIMEOUT_MIN,
        TEST_SETTLE_TIMEOUT_MAX,
        deprecation_executor,
    ])


def test_token_network_variables(token_network, token_network_test_utils):
    max_safe_uint256 = token_network_test_utils.functions.get_max_safe_uint256().call()

    assert token_network.functions.MAX_SAFE_UINT256().call() == max_safe_uint256
    assert max_safe_uint256 == MAX_UINT256

    assert token_network.functions.channel_counter().call() == 0
    assert token_network.functions.signature_prefix().call() == '\x19Ethereum Signed Message:\n'


def test_constructor_not_registered(
        custom_token,
        secret_registry_contract,
        token_network_registry_contract,
        token_network_external,
):
    token_network = token_network_external
    assert token_network.functions.token().call() == custom_token.address
    assert token_network.functions.secret_registry().call() == secret_registry_contract.address
    assert (token_network.functions.chain_id().call()
            == token_network_registry_contract.functions.chain_id().call())

    assert token_network_registry_contract.functions.token_to_token_networks(
        custom_token.address,
    ).call() == EMPTY_ADDRESS
