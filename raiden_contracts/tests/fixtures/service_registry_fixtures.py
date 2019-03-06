import pytest

from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY


@pytest.fixture(scope='session')
def service_registry(deploy_tester_contract, custom_token):
    return deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        {},
        [custom_token.address],
    )
