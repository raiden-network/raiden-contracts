from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import (
    EMPTY_ADDRESS,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.tests.utils.constants import NOT_ADDRESS, UINT256_MAX


def test_constructor_call(
    web3: Web3,
    get_token_network: Callable,
    custom_token: Contract,
    secret_registry_contract: Contract,
    get_accounts: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ Try to deploy TokenNetwork with various wrong arguments """

    (A, deprecation_executor) = get_accounts(2)
    chain_id = web3.eth.chainId
    settle_min = TEST_SETTLE_TIMEOUT_MIN
    settle_max = TEST_SETTLE_TIMEOUT_MAX

    # failure with no arguments
    with pytest.raises(TypeError):
        get_token_network([])

    # failures with integers instead of a Token address
    with pytest.raises(TypeError):
        get_token_network(
            [
                3,
                secret_registry_contract.address,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                0,
                secret_registry_contract.address,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with non-address strings instead of a Token address
    with pytest.raises(TypeError):
        get_token_network(
            [
                "",
                secret_registry_contract.address,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                NOT_ADDRESS,
                secret_registry_contract.address,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with integers instead of a SecretRegistry address
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                3,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                0,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with non-address strings instead of a SecretRegistry address
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                "",
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                NOT_ADDRESS,
                chain_id,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with invalid chain_id
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                "",
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                -3,
                settle_min,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with invalid settle_min
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                chain_id,
                "",
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                chain_id,
                -3,
                settle_max,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with invalid settle_max
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                chain_id,
                settle_min,
                "",
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )
    with pytest.raises(TypeError):
        get_token_network(
            [
                custom_token.address,
                secret_registry_contract.address,
                chain_id,
                settle_min,
                -3,
                deprecation_executor,
                channel_participant_deposit_limit,
                token_network_deposit_limit,
            ]
        )

    # failures with Ethereum addresses that don't contain a Token contract
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=EMPTY_ADDRESS,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=A,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=secret_registry_contract.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failures with Ethereum addresses that don't contain the SecretRegistry contract
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=EMPTY_ADDRESS,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=A,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with chain_id zero
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=0,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with a timeout min and max swapped
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MAX,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MIN,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with settle_timeout_min being zero
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=0,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MIN,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with settle_timeout_max being zero
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=0,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=channel_participant_deposit_limit,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with channel_participant_deposit_limit being zero
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=0,
            _token_network_deposit_limit=token_network_deposit_limit,
        )

    # failure with both limits being zero
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=0,
            _token_network_deposit_limit=0,
        )

    # failure with channel_participant_deposit_limit being bigger than
    # token_network_deposit_limit.
    with pytest.raises(TransactionFailed):
        get_token_network(
            _token_address=custom_token.address,
            _secret_registry=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
            _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
            _deprecation_executor=deprecation_executor,
            _channel_participant_deposit_limit=token_network_deposit_limit,
            _token_network_deposit_limit=channel_participant_deposit_limit,
        )

    # see a success to make sure that the above failures are meaningful
    get_token_network(
        _token_address=custom_token.address,
        _secret_registry=secret_registry_contract.address,
        _chain_id=chain_id,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _deprecation_executor=deprecation_executor,
        _channel_participant_deposit_limit=channel_participant_deposit_limit,
        _token_network_deposit_limit=token_network_deposit_limit,
    )


def test_token_network_variables(
    token_network: Contract, token_network_test_utils: Contract
) -> None:
    """ Check values of storage variables of the TokenNetwork contract """
    max_safe_uint256 = token_network_test_utils.functions.get_max_safe_uint256().call()

    assert token_network.functions.MAX_SAFE_UINT256().call() == max_safe_uint256
    assert max_safe_uint256 == UINT256_MAX

    assert token_network.functions.channel_counter().call() == 0
    assert token_network.functions.signature_prefix().call() == "\x19Ethereum Signed Message:\n"


@pytest.mark.usefixtures("no_token_network")
def test_constructor_not_registered(
    custom_token: Contract,
    secret_registry_contract: Contract,
    token_network_registry_contract: Contract,
    token_network_external: Contract,
) -> None:
    """ Check that the TokenNetwork refers to the right Token address and chain_id """

    token_network = token_network_external
    assert token_network.functions.token().call() == custom_token.address
    assert token_network.functions.secret_registry().call() == secret_registry_contract.address
    assert (
        token_network.functions.chain_id().call()
        == token_network_registry_contract.functions.chain_id().call()
    )

    # The TokenNetworkRegistry doesn't know about the TokenNetwork
    assert (
        token_network_registry_contract.functions.token_to_token_networks(
            custom_token.address
        ).call()
        == EMPTY_ADDRESS
    )
