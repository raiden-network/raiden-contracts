import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_MONITORING_SERVICE


@pytest.fixture(scope="session")
def monitoring_service_external(
    deploy_tester_contract: Contract,
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_MONITORING_SERVICE,
        [
            custom_token.address,
            service_registry.address,
            uninitialized_user_deposit_contract.address,
        ],
    )


@pytest.fixture()
def monitoring_service_internals(
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
    deploy_tester_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "MonitoringServiceInternalsTest",
        [
            custom_token.address,
            service_registry.address,
            uninitialized_user_deposit_contract.address,
        ],
    )
