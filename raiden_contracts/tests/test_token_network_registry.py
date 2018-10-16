import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import (
    CONTRACTS_VERSION,
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from .fixtures.config import (
    EMPTY_ADDRESS,
    FAKE_ADDRESS,
)
from raiden_contracts.utils.events import check_token_network_created
from web3.exceptions import ValidationError


def test_version(token_network_registry_contract):
    version = token_network_registry_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION


def test_constructor_call(
        web3,
        get_token_network_registry,
        secret_registry_contract,
        get_accounts,
):
    A = get_accounts(1)[0]
    chain_id = int(web3.version.network)
    settle_min = TEST_SETTLE_TIMEOUT_MIN
    settle_max = TEST_SETTLE_TIMEOUT_MAX
    with pytest.raises(TypeError):
        get_token_network_registry([])
    with pytest.raises(TypeError):
        get_token_network_registry([3, chain_id, settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([0, chain_id, settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry(['', chain_id, settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([FAKE_ADDRESS, chain_id, settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, '', settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, '1', settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, -3, settle_min, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, '', settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, '1', settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, -3, settle_max])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, settle_min, ''])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, 'settle_min, 1'])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry_contract.address, chain_id, settle_min, -3])

    with pytest.raises(TransactionFailed):
        get_token_network_registry([EMPTY_ADDRESS, chain_id, settle_min, settle_max])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([A, chain_id, settle_min, settle_max])

    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, settle_min, settle_max])

    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, 0, settle_max])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, settle_min, 0])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry_contract.address, 0, settle_max, settle_min])

    get_token_network_registry([
        secret_registry_contract.address,
        chain_id,
        settle_min,
        settle_max,
    ])


def test_constructor_call_state(web3, get_token_network_registry, secret_registry_contract):
    chain_id = int(web3.version.network)

    registry = get_token_network_registry([
        secret_registry_contract.address,
        chain_id,
        TEST_SETTLE_TIMEOUT_MIN,
        TEST_SETTLE_TIMEOUT_MAX,
    ])
    assert secret_registry_contract.address == registry.functions.secret_registry_address().call()
    assert chain_id == registry.functions.chain_id().call()
    assert TEST_SETTLE_TIMEOUT_MIN == registry.functions.settlement_timeout_min().call()
    assert TEST_SETTLE_TIMEOUT_MAX == registry.functions.settlement_timeout_max().call()


def test_create_erc20_token_network_call(
        token_network_registry_contract,
        contract_deployer_address,
        custom_token,
        get_accounts,
):
    A = get_accounts(1)[0]
    fake_token_contract = token_network_registry_contract.address
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork().transact()
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(3).transact()
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(0).transact()
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork('').transact()
    with pytest.raises(ValidationError):
        token_network_registry_contract.functions.createERC20TokenNetwork(FAKE_ADDRESS).transact()

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(EMPTY_ADDRESS).transact()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(A).transact()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            fake_token_contract,
        ).transact()

    token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
    ).transact({'from': contract_deployer_address})


def test_create_erc20_token_network(
        register_token_network,
        token_network_registry_contract,
        custom_token,
):
    assert token_network_registry_contract.functions.token_to_token_networks(
        custom_token.address,
    ).call() == EMPTY_ADDRESS

    token_network = register_token_network(custom_token.address)

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


def test_create_erc20_token_network_twice_fails(
        owner,
        token_network_registry_contract,
        custom_token,

):

    token_network_registry_contract.transact(
        {'from': owner},
    ).createERC20TokenNetwork(
        custom_token.address,
    )

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.transact(
            {'from': owner},
        ).createERC20TokenNetwork(
            custom_token.address,
        )


def test_events(
        register_token_network,
        token_network_registry_contract,
        custom_token,
        event_handler,
):
    ev_handler = event_handler(token_network_registry_contract)

    new_token_network = register_token_network(custom_token.address)

    ev_handler.add(
        None,
        EVENT_TOKEN_NETWORK_CREATED,
        check_token_network_created(custom_token.address, new_token_network.address),
    )
    ev_handler.check()
