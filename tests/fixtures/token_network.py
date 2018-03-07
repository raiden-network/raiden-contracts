import pytest
from utils.config import C_TOKEN_NETWORK


@pytest.fixture()
def get_token_network(chain, create_contract):
    def get(arguments, transaction=None):
        TokenNetwork = chain.provider.get_contract_factory(C_TOKEN_NETWORK)
        contract = create_contract(TokenNetwork, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def token_network(get_token_network, custom_token, secret_registry):
    return get_token_network([custom_token.address, secret_registry.addrress])
