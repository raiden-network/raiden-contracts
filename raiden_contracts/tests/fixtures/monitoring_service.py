import pytest
from raiden_contracts.constants import CONTRACT_MONITORING_SERVICE


@pytest.fixture()
def get_monitoring_service(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            CONTRACT_MONITORING_SERVICE,
            {},
            arguments,
        )
    return get


@pytest.fixture()
def monitoring_service_external(
    get_monitoring_service,
    custom_token,
    raiden_service_bundle,
):
    return get_monitoring_service([
        custom_token.address,
        raiden_service_bundle.address,
    ])
