import pytest
from ethereum import tester
from raiden_contracts.utils.config import C_TOKEN_NETWORK_REGISTRY, C_TOKEN_NETWORK, E_TOKEN_NETWORK_CREATED
from .fixtures.utils import *
from .fixtures.secret_registry import *
from .fixtures.token import *
from .fixtures.token_network_registry import *


def test_version(token_network_registry):
    assert token_network_registry.call().contract_version()[:2] == raiden_contracts_version[:2]


def test_constructor(get_token_network_registry, secret_registry, get_accounts):
    A = get_accounts(1)[0]
    with pytest.raises(TypeError):
        get_token_network_registry([])
    with pytest.raises(TypeError):
        get_token_network_registry([3])
    with pytest.raises(TypeError):
        get_token_network_registry([0])
    with pytest.raises(TypeError):
        get_token_network_registry([''])
    with pytest.raises(TypeError):
        get_token_network_registry([fake_address])

    with pytest.raises(tester.TransactionFailed):
        get_token_network_registry([empty_address])
    with pytest.raises(tester.TransactionFailed):
        get_token_network_registry([A])

    registry = get_token_network_registry([secret_registry.address])
    assert secret_registry.address == registry.call().secret_registry_address()


def test_create_erc20_token_network_call(token_network_registry, custom_token, get_accounts):
    A = get_accounts(1)[0]
    fake_token_contract = token_network_registry.address
    with pytest.raises(TypeError):
        token_network_registry.transact().createERC20TokenNetwork()
    with pytest.raises(TypeError):
        token_network_registry.transact().createERC20TokenNetwork(3)
    with pytest.raises(TypeError):
        token_network_registry.transact().createERC20TokenNetwork(0)
    with pytest.raises(TypeError):
        token_network_registry.transact().createERC20TokenNetwork('')
    with pytest.raises(TypeError):
        token_network_registry.transact().createERC20TokenNetwork(fake_address)

    with pytest.raises(tester.TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(empty_address)
    with pytest.raises(tester.TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(A)
    with pytest.raises(tester.TransactionFailed):
        token_network_registry.transact().createERC20TokenNetwork(fake_token_contract)

    token_network_registry.transact().createERC20TokenNetwork(custom_token.address)


def test_create_erc20_token_network(chain, web3, token_network_registry, custom_token):
    new_token_network = token_network_registry.call().createERC20TokenNetwork(custom_token.address)

    token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    assert new_token_network == token_network_registry.call().token_to_token_networks(
        custom_token.address
    )

    # Check that the token network contract was indeed created
    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    token_network = web3.eth.contract(address=new_token_network, ContractFactoryClass=TokenNetwork)
    assert token_network.call().token() == custom_token.address
    assert token_network.call().secret_registry() == token_network_registry.call().secret_registry_address()


def test_events(token_network_registry, custom_token, event_handler):
    ev_handler = event_handler(token_network_registry)

    new_token_network = token_network_registry.call().createERC20TokenNetwork(custom_token.address)

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    ev_handler.add(txn_hash, E_TOKEN_NETWORK_CREATED, check_token_network_created(custom_token.address, new_token_network))
    ev_handler.check()


def test_print_gas_cost(chain, token_network_registry, custom_token, print_gas):
    TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
    deploy_txn_hash = TokenNetworkRegistry.deploy(args=[custom_token.address])
    print_gas(deploy_txn_hash, C_TOKEN_NETWORK_REGISTRY + ' DEPLOYMENT')

    txn_hash = token_network_registry.transact().createERC20TokenNetwork(custom_token.address)
    print_gas(txn_hash, C_TOKEN_NETWORK_REGISTRY + '.createERC20TokenNetwork')
