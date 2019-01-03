import pytest
from raiden_contracts.constants import CONTRACT_RAIDEN_SERVICE_BUNDLE


@pytest.fixture()
def get_raiden_service_bundle(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            CONTRACT_RAIDEN_SERVICE_BUNDLE,
            {},
            arguments,
        )
    return get


@pytest.fixture()
def raiden_service_bundle(get_raiden_service_bundle, custom_token):
    return get_raiden_service_bundle([
        custom_token.address,
    ])
