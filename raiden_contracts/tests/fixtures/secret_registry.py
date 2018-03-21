import pytest
from raiden_contracts.utils.config import C_SECRET_REGISTRY


@pytest.fixture()
def get_secret_registry(chain, create_contract):
    def get(arguments, transaction=None):
        SecretRegistry = chain.provider.get_contract_factory(C_SECRET_REGISTRY)
        contract = create_contract(SecretRegistry, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def secret_registry(get_secret_registry):
    return get_secret_registry([])
