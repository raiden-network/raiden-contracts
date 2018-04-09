import pytest
from raiden_contracts.utils.config import C_MONITORING_SERVICE


@pytest.fixture()
def get_monitoring_service(chain, create_contract):
    def get(arguments, transaction=None):
        MonitoringService = chain.provider.get_contract_factory(C_MONITORING_SERVICE)
        contract = create_contract(MonitoringService, arguments, transaction)
        return contract
    return get


@pytest.fixture()
def monitoring_service_external(get_token_network, custom_token):
    return get_token_network([
        custom_token.address,
        100
    ])
