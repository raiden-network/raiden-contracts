from typing import Callable

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_SERVICE_REGISTRY, EMPTY_ADDRESS
from raiden_contracts.tests.utils import (
    DEFAULT_BUMP_DENOMINATOR,
    DEFAULT_BUMP_NUMERATOR,
    DEFAULT_DECAY_CONSTANT,
    DEFAULT_MIN_PRICE,
    DEFAULT_REGISTRATION_DURATION,
    DEPLOYER_ADDRESS,
)


@pytest.fixture(scope="session")
def service_registry(deploy_tester_contract: Callable, custom_token: Contract) -> Contract:
    return deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        _token_for_registration=custom_token.address,
        _controller=DEPLOYER_ADDRESS,
        _initial_price=int(3000e18),
        _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
        _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
        _decay_constant=DEFAULT_DECAY_CONSTANT,
        _min_price=DEFAULT_MIN_PRICE,
        _registration_duration=DEFAULT_REGISTRATION_DURATION,
    )


@pytest.fixture(scope="session")
def service_registry_without_controller(
    deploy_tester_contract: Callable, custom_token: Contract
) -> Contract:
    return deploy_tester_contract(
        CONTRACT_SERVICE_REGISTRY,
        _token_for_registration=custom_token.address,
        _controller=EMPTY_ADDRESS,
        _initial_price=3000 * (10 ** 18),
        _price_bump_numerator=DEFAULT_BUMP_NUMERATOR,
        _price_bump_denominator=DEFAULT_BUMP_DENOMINATOR,
        _decay_constant=DEFAULT_DECAY_CONSTANT,
        _min_price=DEFAULT_MIN_PRICE,
        _registration_duration=DEFAULT_REGISTRATION_DURATION,
    )
