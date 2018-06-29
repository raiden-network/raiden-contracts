import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import (
    EVENT_TOKEN_NETWORK_CREATED,
    TEST_SETTLE_TIMEOUT_MIN,
    TEST_SETTLE_TIMEOUT_MAX,
)
from .fixtures.config import (
    raiden_contracts_version,
    empty_address,
    fake_address,
)
from raiden_contracts.utils.events import check_token_network_created
from web3.exceptions import ValidationError


def test_version(token_network_registry_contract):
    assert (token_network_registry_contract.functions.contract_version().call()[:2]
            == raiden_contracts_version[:2])


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
        get_token_network_registry([fake_address, chain_id, settle_min, settle_max])
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
        get_token_network_registry([empty_address, chain_id, settle_min, settle_max])
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


def test_create_erc20_token_network_call(
        token_network_registry_contract,
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
        token_network_registry_contract.functions.createERC20TokenNetwork(fake_address).transact()

    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(empty_address).transact()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(A).transact()
    with pytest.raises(TransactionFailed):
        token_network_registry_contract.functions.createERC20TokenNetwork(
            fake_token_contract,
        ).transact()

    token_network_registry_contract.functions.createERC20TokenNetwork(
        custom_token.address,
    ).transact()


def test_create_erc20_token_network(
        register_token_network,
        token_network_registry_contract,
        custom_token,
        get_accounts,
):
    assert token_network_registry_contract.functions.token_to_token_networks(
        custom_token.address).call() == empty_address

    token_network = register_token_network(custom_token.address)

    assert token_network.functions.token().call() == custom_token.address
    secret_registry_address = token_network_registry_contract.functions.secret_registry_address().call()  # noqa
    assert token_network.functions.secret_registry().call() == secret_registry_address
    assert (token_network.functions.chain_id().call()
            == token_network_registry_contract.functions.chain_id().call())


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
