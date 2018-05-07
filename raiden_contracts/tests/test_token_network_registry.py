import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.utils.config import E_TOKEN_NETWORK_CREATED
from .fixtures.config import (
    raiden_contracts_version,
    empty_address,
    fake_address
)
from raiden_contracts.utils.events import check_token_network_created
from web3.exceptions import ValidationError


def test_version(token_network_registry):
    assert token_network_registry.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_constructor_call(web3, get_token_network_registry, secret_registry, get_accounts):
    A = get_accounts(1)[0]
    chain_id = int(web3.version.network)
    with pytest.raises(TypeError):
        get_token_network_registry([])
    with pytest.raises(TypeError):
        get_token_network_registry([3, chain_id])
    with pytest.raises(TypeError):
        get_token_network_registry([0, chain_id])
    with pytest.raises(TypeError):
        get_token_network_registry(['', chain_id])
    with pytest.raises(TypeError):
        get_token_network_registry([fake_address, chain_id])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry.address, ''])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry.address, '1'])
    with pytest.raises(TypeError):
        get_token_network_registry([secret_registry.address, -3])

    with pytest.raises(TransactionFailed):
        get_token_network_registry([empty_address, chain_id])
    with pytest.raises(TransactionFailed):
        get_token_network_registry([A, chain_id])

    with pytest.raises(TransactionFailed):
        get_token_network_registry([secret_registry.address, 0])

    get_token_network_registry([secret_registry.address, chain_id])


def test_constructor_call_state(web3, get_token_network_registry, secret_registry):
    chain_id = int(web3.version.network)

    registry = get_token_network_registry([secret_registry.address, chain_id])
    assert secret_registry.address == registry.call().secret_registry_address()
    assert chain_id == registry.call().chain_id()


def test_create_erc20_token_network_call(token_network_registry, custom_token, get_accounts):
    A = get_accounts(1)[0]
    fake_token_contract = token_network_registry.address
    with pytest.raises(ValidationError):
        token_network_registry.transact().createERC20TokenNetwork()
    with pytest.raises(ValidationError):
        token_network_registry.transact().createERC20TokenNetwork(3)
    with pytest.raises(ValidationError):
        token_network_registry.transact().createERC20TokenNetwork(0)
    with pytest.raises(ValidationError):
        token_network_registry.transact().createERC20TokenNetwork('')
    with pytest.raises(ValidationError):
        token_network_registry.transact().createERC20TokenNetwork(fake_address)

    with pytest.raises(TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(empty_address)
    with pytest.raises(TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(A)
    with pytest.raises(TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(fake_token_contract)

    token_network_registry.transact().createERC20TokenNetwork(custom_token.address)


def test_create_erc20_token_network(
        register_token_network,
        token_network_registry,
        custom_token,
        get_accounts
):
    assert token_network_registry.call().token_to_token_networks(
        custom_token.address) == empty_address

    token_network = register_token_network(custom_token.address)

    assert token_network.call().token() == custom_token.address
    secret_registry_address = token_network_registry.call().secret_registry_address()
    assert token_network.call().secret_registry() == secret_registry_address
    assert token_network.call().chain_id() == token_network_registry.call().chain_id()


def test_events(register_token_network, token_network_registry, custom_token, event_handler):
    ev_handler = event_handler(token_network_registry)

    new_token_network = register_token_network(custom_token.address)

    ev_handler.add(
        None,
        E_TOKEN_NETWORK_CREATED,
        check_token_network_created(custom_token.address, new_token_network.address)
    )
    ev_handler.check()
