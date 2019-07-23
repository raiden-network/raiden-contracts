from typing import Callable

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY, EMPTY_ADDRESS
from raiden_contracts.tests.utils import (
    CONTRACT_DEPLOYER_ADDRESS,
    DEFAULT_BUMP_DENOMINATOR,
    DEFAULT_BUMP_NUMERATOR,
    DEFAULT_DECAY_CONSTANT,
    DEFAULT_MIN_PRICE,
    DEFAULT_REGISTRATION_DURATION,
)


@pytest.fixture(scope="session")
def service_registry(deploy_tester_contract: Callable, custom_token: Contract) -> Contract:
    return deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        [
            custom_token.address,
            CONTRACT_DEPLOYER_ADDRESS,
            int(3000e18),
            DEFAULT_BUMP_NUMERATOR,
            DEFAULT_BUMP_DENOMINATOR,
            DEFAULT_DECAY_CONSTANT,
            DEFAULT_MIN_PRICE,
            DEFAULT_REGISTRATION_DURATION,
        ],
    )


@pytest.fixture(scope="session")
def service_registry_without_controller(
    deploy_tester_contract: Callable, custom_token: Contract
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        [
            custom_token.address,
            EMPTY_ADDRESS,
            3000 * (10 ** 18),
            DEFAULT_BUMP_NUMERATOR,
            DEFAULT_BUMP_DENOMINATOR,
            DEFAULT_DECAY_CONSTANT,
            DEFAULT_MIN_PRICE,
            DEFAULT_REGISTRATION_DURATION,
        ],
    )
