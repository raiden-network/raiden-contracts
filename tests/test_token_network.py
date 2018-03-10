import pytest
from ethereum import tester
from utils.config import C_TOKEN_NETWORK
from tests.fixtures.utils import *
from tests.fixtures.token_network import *
from tests.fixtures.token import *
from tests.fixtures.secret_registry import *


def test_version(token_network):
    assert token_network.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_constructor_call(get_token_network, custom_token, secret_registry, get_accounts):
    A = get_accounts(1)[0]
    with pytest.raises(TypeError):
        get_token_network([])
    with pytest.raises(TypeError):
        get_token_network([3, secret_registry.address])
    with pytest.raises(TypeError):
        get_token_network([0, secret_registry.address])
    with pytest.raises(TypeError):
        get_token_network(['', secret_registry.address])
    with pytest.raises(TypeError):
        get_token_network([fake_address, secret_registry.address])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 3])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 0])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, ''])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, fake_address])

    with pytest.raises(tester.TransactionFailed):
        get_token_network([empty_address, secret_registry.address])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([A, secret_registry.address])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([secret_registry.address, secret_registry.address])

    with pytest.raises(tester.TransactionFailed):
        get_token_network([custom_token.address, empty_address])
    with pytest.raises(tester.TransactionFailed):
        get_token_network([custom_token.address, A])

    token_network = get_token_network([custom_token.address, secret_registry.address])


def test_constructor(get_token_network, custom_token, secret_registry):
    token_network = get_token_network([custom_token.address, secret_registry.address])
    assert token_network.call().token() == custom_token.address
    assert token_network.call().secret_registry() == secret_registry.address


def test_print_gas_cost(chain, print_gas, custom_token, secret_registry):
    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    deploy_txn_hash = TokenNetwork.deploy(args=[
        custom_token.address,
        secret_registry.address
    ])

    print_gas(deploy_txn_hash, C_TOKEN_NETWORK + ' DEPLOYMENT')
