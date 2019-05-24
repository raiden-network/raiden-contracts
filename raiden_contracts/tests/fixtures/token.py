from typing import Callable, List, Tuple

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_HUMAN_STANDARD_TOKEN

CUSTOM_TOKEN_TOTAL_SUPPLY = 10 ** 26


@pytest.fixture(scope="session")
def token_args() -> Tuple:
    return (CUSTOM_TOKEN_TOTAL_SUPPLY, 18, CONTRACT_CUSTOM_TOKEN, "TKN")


@pytest.fixture(scope="session")
def custom_token_factory(deploy_tester_contract: Callable, token_args: List) -> Callable:
    """A function that deploys a CustomToken contract"""

    def f() -> Contract:
        return deploy_tester_contract(CONTRACT_CUSTOM_TOKEN, token_args)

    return f


@pytest.fixture(scope="session")
def custom_token(custom_token_factory: Callable) -> Contract:
    """Deploy CustomToken contract"""
    return custom_token_factory()


@pytest.fixture()
def human_standard_token(deploy_token_contract: Callable, token_args: List) -> Contract:
    """Deploy HumanStandardToken contract"""
    return deploy_token_contract(*token_args)


@pytest.fixture
def deploy_token_contract(deploy_tester_contract: Contract) -> Callable:
    """Returns a function that deploys a generic HumanStandardToken contract"""

    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str) -> Contract:
        assert initial_amount > 0
        assert decimals > 0
        return deploy_tester_contract(
            CONTRACT_HUMAN_STANDARD_TOKEN, [initial_amount, decimals, token_name, token_symbol]
        )

    return f


@pytest.fixture
def standard_token_contract(custom_token: Contract) -> Contract:
    """Deployed CustomToken contract"""
    return custom_token
