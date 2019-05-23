from typing import Callable

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY


@pytest.fixture(scope="session")
def service_registry(deploy_tester_contract: Callable, custom_token: Contract) -> Contract:
    return deploy_tester_contract(CONTRACT_SERVICE_REGISTRY, [custom_token.address])
