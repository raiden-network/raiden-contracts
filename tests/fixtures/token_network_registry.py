import pytest
from utils.config import C_TOKEN_NETWORK_REGISTRY


@pytest.fixture()
def get_token_network_registry(chain, create_contract):
    def get(arguments, transaction=None):
        TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
        contract = create_contract(TokenNetworkRegistry, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def token_network_registry(get_token_network_registry, secret_registry):
    return get_token_network_registry([secret_registry.addrress])
