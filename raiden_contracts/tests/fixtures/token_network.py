import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK


@pytest.fixture()
def get_token_network(chain, create_contract):
    def get(arguments, transaction=None):
        TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
        contract = create_contract(TokenNetwork, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def token_network(chain, token_network_registry, custom_token, secret_registry):
    token_network_address = token_network_registry.call().createERC20TokenNetwork(
        custom_token.address
    )
    token_network_registry.transact().createERC20TokenNetwork(custom_token.address)

    TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
    token_network = chain.web3.eth.contract(
        address=token_network_address,
        ContractFactoryClass=TokenNetwork
    )

    return token_network


@pytest.fixture()
def token_network_external(chain, get_token_network, custom_token, secret_registry):
    return get_token_network([
        custom_token.address,
        secret_registry.address,
        int(chain.web3.version.network)
    ])
