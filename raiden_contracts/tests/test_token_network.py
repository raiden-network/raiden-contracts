import pytest
from eth_tester.exceptions import TransactionFailed
from .fixtures.config import raiden_contracts_version, empty_address, fake_address


def test_version(token_network):
    assert token_network.functions.contract_version().call()[:2] == raiden_contracts_version[:2]


def test_constructor_call(
        web3,
        get_token_network,
        custom_token,
        secret_registry_contract,
        get_accounts,
):
    A = get_accounts(1)[0]
    chain_id = int(web3.version.network)
    with pytest.raises(TypeError):
        get_token_network([])
    with pytest.raises(TypeError):
        get_token_network([3, secret_registry_contract.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([0, secret_registry_contract.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network(['', secret_registry_contract.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([fake_address, secret_registry_contract.address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 3, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, 0, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, '', chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, fake_address, chain_id])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, secret_registry_contract.address, ''])
    with pytest.raises(TypeError):
        get_token_network([custom_token.address, secret_registry_contract.address, -3])

    with pytest.raises(TransactionFailed):
        get_token_network([empty_address, secret_registry_contract.address, chain_id])
    with pytest.raises(TransactionFailed):
        get_token_network([A, secret_registry_contract.address, chain_id])
    with pytest.raises(TransactionFailed):
        get_token_network(
            [secret_registry_contract.address, secret_registry_contract.address, chain_id],
        )

    with pytest.raises(TransactionFailed):
        get_token_network([custom_token.address, empty_address, chain_id])
    with pytest.raises(TransactionFailed):
        get_token_network([custom_token.address, A, chain_id])

    with pytest.raises(TransactionFailed):
        get_token_network([custom_token.address, secret_registry_contract.address, 0])

    get_token_network([custom_token.address, secret_registry_contract.address, chain_id])


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
    ).call() == empty_address
