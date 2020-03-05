from typing import Callable

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_MONITORING_SERVICE


@pytest.fixture(scope="session")
def monitoring_service_external(
    deploy_tester_contract: Callable,
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
    token_network_registry_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_MONITORING_SERVICE,
        _token_address=custom_token.address,
        _service_registry_address=service_registry.address,
        _udc_address=uninitialized_user_deposit_contract.address,
        _token_network_registry_address=token_network_registry_contract.address,
    )


@pytest.fixture()
def monitoring_service_internals(
    custom_token: Contract,
    service_registry: Contract,
    uninitialized_user_deposit_contract: Contract,
    deploy_tester_contract: Callable,
    token_network_registry_contract: Contract,
) -> Contract:
    return deploy_tester_contract(
        "MonitoringServiceInternalsTest",
        _token_address=custom_token.address,
        _service_registry_address=service_registry.address,
        _udc_address=uninitialized_user_deposit_contract.address,
        _token_network_registry_address=token_network_registry_contract.address,
    )
