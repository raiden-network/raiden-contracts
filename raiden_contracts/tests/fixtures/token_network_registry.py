import pytest
from raiden_contracts.utils.config import C_TOKEN_NETWORK_REGISTRY
from .utils import *  # flake8: noqa


@pytest.fixture()
def get_token_network_registry(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            C_TOKEN_NETWORK_REGISTRY,
            {},
            arguments
        )
    return get


@pytest.fixture()
def token_network_registry(token_network_registry_contract):
    return token_network_registry_contract
