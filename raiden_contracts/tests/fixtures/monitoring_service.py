import pytest
from raiden_contracts.utils.config import C_MONITORING_SERVICE


@pytest.fixture()
def get_monitoring_service(deploy_tester_contract):
    def get(arguments, transaction=None):
        return deploy_tester_contract(
            C_MONITORING_SERVICE,
            {},
            arguments
        )
    return get


@pytest.fixture()
def monitoring_service_external(get_monitoring_service, custom_token):
    return get_monitoring_service([
        custom_token.address,
        10
    ])
