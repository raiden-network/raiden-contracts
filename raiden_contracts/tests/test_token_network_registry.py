from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ValidationError

from raiden_contracts.constants import (
    EMPTY_ADDRESS,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.constants import DEPLOYER_ADDRESS, NOT_ADDRESS
from raiden_contracts.utils.events import check_token_network_created


@pytest.mark.usefixtures("no_token_network")
def test_constructor_call(
    web3: Web3,
    get_token_network_registry: Callable,
    secret_registry_contract: Contract,
    get_accounts: Callable,
) -> None:
    """ Try to create a TokenNetworkRegistry with various wrong arguments. """
    A = get_accounts(1)[0]
    chain_id = web3.eth.chainId
    settle_min = TEST_SETTLE_TIMEOUT_MIN
    settle_max = TEST_SETTLE_TIMEOUT_MAX

    # failure with no arguments
    with pytest.raises(TypeError):
        get_token_network_registry()

    # failure with an int instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=3,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with zero instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=0,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with the empty string instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address="",
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with an odd-length hex string instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=NOT_ADDRESS,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with the empty string instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id="",
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with a string instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id="1",
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with a negative integer instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=-3,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with chain ID zero
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=0,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failure with strings instead of the minimal challenge period
    with pytest.raises(TypeError):
        get_token_network_registry(
            [secret_registry_contract.address, chain_id, "", settle_max, 1, 1]
        )
    with pytest.raises(TypeError):
        get_token_network_registry(
            [secret_registry_contract.address, chain_id, "1", settle_max, 1, 1]
        )
    with pytest.raises(TypeError):
        get_token_network_registry(
            [secret_registry_contract.address, chain_id, -3, settle_max, 1, 1]
        )

    # failure with strings instead of the max challenge period
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max="",
            _max_token_networks=1,
        )
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min="settle_min,1",
            _max_token_networks=1,
        )
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=-3,
            _max_token_networks=1,
        )

    # failure with Ethereum accounts that doesn't look like a SecretRegistry
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=EMPTY_ADDRESS,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=A,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )

    # failures with chain_id zero
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=0,
            _settlement_timeout_min=0,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=0,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=0,
            _max_token_networks=1,
        )
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=0,
            _settlement_timeout_min=settle_max,
            _settlement_timeout_max=settle_min,
            _max_token_networks=1,
        )

    # failures with nonsense challenge periods
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=0,
            _settlement_timeout_max=settle_max,
            _max_token_networks=1,
        )
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_min,
            _settlement_timeout_max=0,
            _max_token_networks=1,
        )
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=settle_max,
            _settlement_timeout_max=settle_min,
            _max_token_networks=1,
        )

    # failures with nonsense token number limits
    with pytest.raises(TransactionFailed):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=0,
            _settlement_timeout_max=settle_max,
            _max_token_networks=0,
        )
    with pytest.raises(TypeError):
        get_token_network_registry(
            _secret_registry_address=secret_registry_contract.address,
            _chain_id=chain_id,
            _settlement_timeout_min=0,
            _settlement_timeout_max=settle_max,
            _max_token_networks="limit",
        )

    get_token_network_registry(
        _secret_registry_address=secret_registry_contract.address,
        _chain_id=chain_id,
        _settlement_timeout_min=settle_min,
        _settlement_timeout_max=settle_max,
        _max_token_networks=1,
    )


@pytest.mark.usefixtures("no_token_network")
def test_constructor_call_state(
    web3: Web3, get_token_network_registry: Callable, secret_registry_contract: Contract
) -> None:
    """ The constructor should set the parameters into the storage of the contract """

    chain_id = web3.eth.chainId

    registry = get_token_network_registry(
        _secret_registry_address=secret_registry_contract.address,
        _chain_id=chain_id,
        _settlement_timeout_min=TEST_SETTLE_TIMEOUT_MIN,
        _settlement_timeout_max=TEST_SETTLE_TIMEOUT_MAX,
        _max_token_networks=30,
    )
    assert secret_registry_contract.address == registry.functions.secret_registry_address().call()
    assert chain_id == registry.functions.chain_id().call()
    assert TEST_SETTLE_TIMEOUT_MIN == registry.functions.settlement_timeout_min().call()
    assert TEST_SETTLE_TIMEOUT_MAX == registry.functions.settlement_timeout_max().call()
    assert 30 == registry.functions.max_token_networks().call()


@pytest.mark.usefixtures("no_token_network")
def test_create_erc20_token_network_call(
    token_network_registry_contract: Contract,
    custom_token: Contract,
    get_accounts: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ Calling createERC20TokenNetwork() with various wrong arguments """

    A = get_accounts(1)[0]
    fake_token_contract = token_network_registry_contract.address

    # failure with no arguments
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork()

    # failures with integers instead of a Token contract address
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            3, channel_participant_deposit_limit, token_network_deposit_limit
        )
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            0, channel_participant_deposit_limit, token_network_deposit_limit
        )

    # failures with strings that are not addresses
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            "", channel_participant_deposit_limit, token_network_deposit_limit
        )
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            NOT_ADDRESS, channel_participant_deposit_limit, token_network_deposit_limit
        )

    # failures with addresses where no Token contract can be found
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            EMPTY_ADDRESS, channel_participant_deposit_limit, token_network_deposit_limit
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            A, channel_participant_deposit_limit, token_network_deposit_limit
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            fake_token_contract, channel_participant_deposit_limit, token_network_deposit_limit
        ).call()

    # failures with invalid deposit limits
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, 0, token_network_deposit_limit
        ).call({"from": DEPLOYER_ADDRESS})

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, channel_participant_deposit_limit, 0
        ).call({"from": DEPLOYER_ADDRESS})

    with pytest.raises(TransactionFailed):
        # fails because token_network_deposit_limit is smaller than
        # channel_participant_deposit_limit.
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, token_network_deposit_limit, channel_participant_deposit_limit
        ).call({"from": DEPLOYER_ADDRESS})

    # see a success to make sure above tests were meaningful
    call_and_transact(
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, channel_participant_deposit_limit, token_network_deposit_limit
        ),
        {"from": DEPLOYER_ADDRESS},
    )


@pytest.mark.usefixtures("no_token_network")
def test_create_erc20_token_network(
    register_token_network: Callable,
    token_network_registry_contract: Contract,
    custom_token: Contract,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ Create a TokenNetwork through a TokenNetworkRegistry """

    assert (
        token_network_registry_contract.functions.token_to_token_networks(
            custom_token.address
        ).call()
        == EMPTY_ADDRESS
    )

    token_network = register_token_network(
        token_network_registry=token_network_registry_contract,
        token_address=custom_token.address,
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )

    assert token_network.functions.token().call() == custom_token.address
    assert (
        token_network_registry_contract.functions.token_to_token_networks(
            custom_token.address
        ).call()
        == token_network.address
    )

    secret_registry = token_network_registry_contract.functions.secret_registry_address().call()
    assert token_network.functions.secret_registry().call() == secret_registry

    chain_id = token_network_registry_contract.functions.chain_id().call()
    assert token_network.functions.chain_id().call() == chain_id

    settle_timeout_min = token_network_registry_contract.functions.settlement_timeout_min().call()
    assert token_network.functions.settlement_timeout_min().call() == settle_timeout_min

    settle_timeout_max = token_network_registry_contract.functions.settlement_timeout_max().call()
    assert token_network.functions.settlement_timeout_max().call() == settle_timeout_max


@pytest.mark.usefixtures("no_token_network")
def test_create_erc20_token_network_twice_fails(
    token_network_registry_contract: Contract,
    custom_token: Contract,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ Only one TokenNetwork should be creatable from a TokenNetworkRegistry """

    call_and_transact(
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, channel_participant_deposit_limit, token_network_deposit_limit
        ),
        {"from": DEPLOYER_ADDRESS},
    )

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address, channel_participant_deposit_limit, token_network_deposit_limit
        ).call({"from": DEPLOYER_ADDRESS})


@pytest.mark.usefixtures("no_token_network")
def test_events(
    register_token_network: Callable,
    token_network_registry_contract: Contract,
    custom_token: Contract,
    event_handler: Callable,
    channel_participant_deposit_limit: int,
    token_network_deposit_limit: int,
) -> None:
    """ TokenNetworkRegistry should raise an event when deploying a new TokenNetwork """

    ev_handler = event_handler(token_network_registry_contract)

    new_token_network = register_token_network(
        token_network_registry=token_network_registry_contract,
        token_address=custom_token.address,
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )

    ev_handler.add(
        None,
        EVENT_TOKEN_NETWORK_CREATED,
        check_token_network_created(custom_token.address, new_token_network.address),
    )
    ev_handler.check()
