import pytest
from ethereum import tester
from .fixtures.config import raiden_contracts_version, empty_address, fake_address


def test_version(token_network):
    assert token_network.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_constructor_call(chain, get_token_network, custom_token, secret_registry, get_accounts):
    A = get_accounts(1)[0]
    chain_id = int(chain.web3.version.network)
    with pytest.raises(TypeError):
        get_token_network([])
    with pytest.raises(TypeError):
        get_token_network([3, secret_registry.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([0, secret_registry.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network(['', secret_registry.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([fake_address, secret_registry.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 3, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 0, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, '', chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, fake_address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, secret_registry.address, ''])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, secret_registry.address, -3])

    with pytest.raises(tester.TransactionFailed):
        get_token_network([empty_address, secret_registry.address, chain_id])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([A, secret_registry.address, chain_id])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([secret_registry.address, secret_registry.address, chain_id])

    with pytest.raises(tester.TransactionFailed):
        get_token_network([custom_token.address, empty_address, chain_id])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([custom_token.address, A, chain_id])

    with pytest.raises(tester.TransactionFailed):
        get_token_network([custom_token.address, secret_registry.address, 0])

    get_token_network([custom_token.address, secret_registry.address, chain_id])


def test_constructor_not_registered(
        custom_token,
        secret_registry,
        token_network_registry,
        token_network_external
):
    token_network = token_network_external
    assert token_network.call().token() == custom_token.address
    assert token_network.call().secret_registry() == secret_registry.address
    assert token_network.call().chain_id() == token_network_registry.call().chain_id()

    assert token_network_registry.call().token_to_token_networks(
        custom_token.address
    ) == empty_address
