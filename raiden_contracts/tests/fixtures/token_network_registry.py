import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK_REGISTRY
from .utils import *


@pytest.fixture()
def get_token_network_registry(chain, create_contract):
    def get(arguments, transaction=None):
        TokenNetworkRegistry = chain.provider.get_contract_factory(C_TOKEN_NETWORK_REGISTRY)
        contract = create_contract(TokenNetworkRegistry, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def token_network_registry(chain, get_token_network_registry, secret_registry):
    return get_token_network_registry([secret_registry.address, int(chain.web3.version.network)])


def check_token_network_created(token_address, token_network_address):
    def get(event):
        assert event['args']['token_address'] == token_address
        assert event['args']['token_network_address'] == token_network_address
    return get
