import pytest
from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY


@pytest.fixture()
def get_service_registry(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            CONTRACT_SERVICE_REGISTRY,
            {},
            arguments,
        )
    return get


@pytest.fixture()
def service_registry(get_service_registry, custom_token):
    return get_service_registry([
        custom_token.address,
    ])
