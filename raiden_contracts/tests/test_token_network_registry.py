import pytest
from eth_tester.exceptions import TransactionFailed
from web3.exceptions import ValidationError

from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MAX,
    TEST_SETTLE_TIMEOUT_MIN,
)
from raiden_contracts.tests.utils.constants import (
    CONTRACT_DEPLOYER_ADDRESS,
    EMPTY_ADDRESS,
    FAKE_ADDRESS,
)
from raiden_contracts.utils.events import check_token_network_created


def test_version(token_network_registry_contract):
    """ Check the result of contract_version() call on the TokenNetworkRegistry """
    version = token_network_registry_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION


@pytest.mark.usefixtures('no_token_network')
def test_constructor_call(
        web3,
        get_token_network_registry,
        secret_registry_contract,
        get_accounts,
):
    """ Try to create a TokenNetworkRegistry with various wrong arguments. """
    A = get_accounts(1)[0]
    chain_id = int(web3.version.network)
    settle_min = TEST_SETTLE_TIMEOUT_MIN
    settle_max = TEST_SETTLE_TIMEOUT_MAX

    # failure with no arguments
    with pytest.raises(TypeError):
        get_token_network_registry([])

    # failure with an int instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry([3, chain_id, settle_min, settle_max, 1])

    # failure with zero instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry([0, chain_id, settle_min, settle_max, 1])

    # failure with the empty string instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry(['', chain_id, settle_min, settle_max, 1])

    # failure with an odd-length hex string instead of the SecretRegistry's address
    with pytest.raises(TypeError):
        get_token_network_registry([FAKE_ADDRESS, chain_id, settle_min, settle_max, 1])

    # failure with the empty string instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            '',
            settle_min,
            settle_max,
            1,
        ])

    # failure with a string instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            '1',
            settle_min,
            settle_max,
            1,
        ])

    # failure with a negative integer instead of a chain ID
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            -3,
            settle_min,
            settle_max,
            1,
        ])

    # failure with chain ID zero
    with pytest.raises(TransactionFailed):
        get_token_network_registry([
            secret_registry_contract.address,
            0,
            settle_min,
            settle_max,
            1,
        ])

    # failure with strings instead of the minimal challenge period
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            '',
            settle_max,
            1,
            1,
        ])
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            '1',
            settle_max,
            1,
            1,
        ])
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            -3,
            settle_max,
            1,
            1,
        ])

    # failure with strings instead of the max challenge period
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, settle_min, '', 1])
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            'settle_min, 1',
            1])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, settle_min, -3, 1])

    # failure with Ethereum accounts that doesn't look like a SecretRegistry
    with pytest.raises(TransactionFailed):
        get_token_network_registry([EMPTY_ADDRESS, chain_id, settle_min, settle_max, 1])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([A, chain_id, settle_min, settle_max, 1])

    # failures with chain_id zero
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, 0, settle_max, 1])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, settle_min, 0, 1])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([
            secret_registry_contract.address,
            0,
            settle_max,
            settle_min,
            1,
        ])

    # failures with nonsense challenge periods
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, chain_id, 0, settle_max, 1])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, chain_id, settle_min, 0, 1])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            settle_max,
            settle_min,
            1,
        ])

    # failures with nonsense token number limits
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, chain_id, 0, settle_max, 0])
    with pytest.raises(TypeError):
        get_token_network_registry([
            secret_registry_contract.address,
            chain_id,
            0,
            settle_max,
            'limit',
        ])

    get_token_network_registry([
        secret_registry_contract.address,
        chain_id,
        settle_min,
        settle_max,
        1,
    ])


@pytest.mark.usefixtures('no_token_network')
def test_constructor_call_state(web3, get_token_network_registry, secret_registry_contract):
    """ The constructor should set the parameters into the storage of the contract """

    chain_id = int(web3.version.network)

    registry = get_token_network_registry([
        secret_registry_contract.address,
        chain_id,
        TEST_SETTLE_TIMEOUT_MIN,
        TEST_SETTLE_TIMEOUT_MAX,
        30,
    ])
    assert secret_registry_contract.address == registry.functions.secret_registry_address().call()
    assert chain_id == registry.functions.chain_id().call()
    assert TEST_SETTLE_TIMEOUT_MIN == registry.functions.settlement_timeout_min().call()
    assert TEST_SETTLE_TIMEOUT_MAX == registry.functions.settlement_timeout_max().call()
    assert 30 == registry.functions.max_token_networks().call()


@pytest.mark.usefixtures('no_token_network')
def test_create_erc20_token_network_call(
        token_network_registry_contract,
        custom_token,
        get_accounts,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Calling createERC20TokenNetwork() with various wrong arguments """

    A = get_accounts(1)[0]
    fake_token_contract = token_network_registry_contract.address

    # failure with no arguments
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork()

    # failures with integers instead of a Token contract address
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            3,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            0,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )

    # failures with strings that are not addresses
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            '',
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            FAKE_ADDRESS,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        )

    # failures with addresses where no Token contract can be found
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            EMPTY_ADDRESS,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            A,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            fake_token_contract,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call()

    # failures with invalid deposit limits
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address,
            0,
            token_network_deposit_limit,
        ).call({'from': CONTRACT_DEPLOYER_ADDRESS})

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            0,
        ).call({'from': CONTRACT_DEPLOYER_ADDRESS})

    with pytest.raises(TransactionFailed):
        # fails because token_network_deposit_limit is smaller than
        # channel_participant_deposit_limit.
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address,
            token_network_deposit_limit,
            channel_participant_deposit_limit,
        ).call({'from': CONTRACT_DEPLOYER_ADDRESS})

    # see a success to make sure above tests were meaningful
    token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact({'from': CONTRACT_DEPLOYER_ADDRESS})


@pytest.mark.usefixtures('no_token_network')
def test_create_erc20_token_network(
        register_token_network,
        token_network_registry_contract,
        custom_token,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Create a TokenNetwork through a TokenNetworkRegistry """

    assert token_network_registry_contract.functions.token_to_token_networks(
        custom_token.address,
    ).call() == EMPTY_ADDRESS

    token_network = register_token_network(
        token_address=custom_token.address,
        channel_participant_deposit_limit=channel_participant_deposit_limit,
        token_network_deposit_limit=token_network_deposit_limit,
    )

    assert token_network.functions.token().call() == custom_token.address
    assert token_network_registry_contract.functions.token_to_token_networks(
        custom_token.address,
    ).call() == token_network.address

    secret_registry = token_network_registry_contract.functions.secret_registry_address().call()
    assert token_network.functions.secret_registry().call() == secret_registry

    chain_id = token_network_registry_contract.functions.chain_id().call()
    assert token_network.functions.chain_id().call() == chain_id

    settle_timeout_min = token_network_registry_contract.functions.settlement_timeout_min().call()
    assert token_network.functions.settlement_timeout_min().call() == settle_timeout_min

    settle_timeout_max = token_network_registry_contract.functions.settlement_timeout_max().call()
    assert token_network.functions.settlement_timeout_max().call() == settle_timeout_max


@pytest.mark.usefixtures('no_token_network')
def test_create_erc20_token_network_twice_fails(
        token_network_registry_contract,
        custom_token,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ Only one TokenNetwork should be creatable from a TokenNetworkRegistry """

    token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
    ).call_and_transact({'from': CONTRACT_DEPLOYER_ADDRESS})

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            custom_token.address,
            channel_participant_deposit_limit,
            token_network_deposit_limit,
        ).call(
            {'from': CONTRACT_DEPLOYER_ADDRESS},
        )


@pytest.mark.usefixtures('no_token_network')
def test_events(
        register_token_network,
        token_network_registry_contract,
        custom_token,
        event_handler,
        channel_participant_deposit_limit,
        token_network_deposit_limit,
):
    """ TokenNetwokRegistry should raise an event when deploying a new TokenNetwork """

    ev_handler = event_handler(token_network_registry_contract)

    new_token_network = register_token_network(
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
