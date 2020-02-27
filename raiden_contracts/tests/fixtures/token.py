from typing import Callable, Dict

import pytest
from web3.contract import Contract

from raiden_contracts.constants import CONTRACT_CUSTOM_TOKEN, CONTRACT_HUMAN_STANDARD_TOKEN

CUSTOM_TOKEN_TOTAL_SUPPLY = 10 ** 26


@pytest.fixture(scope="session")
def token_args() -> Dict:
    return {
        "initial_supply": CUSTOM_TOKEN_TOTAL_SUPPLY,
        "decimal_units": 18,
        "token_name": CONTRACT_CUSTOM_TOKEN,
        "token_symbol": "TKN",
    }


@pytest.fixture(scope="session")
def custom_token_factory(deploy_tester_contract: Callable, token_args: Dict) -> Callable:
    """A function that deploys a CustomToken contract"""

    def f() -> Contract:
        return deploy_tester_contract(CONTRACT_CUSTOM_TOKEN, **token_args)

    return f


@pytest.fixture(scope="session")
def custom_token(custom_token_factory: Callable) -> Contract:
    """Deploy CustomToken contract"""
    return custom_token_factory()


@pytest.fixture(scope="session")
def zero_supply_custom_token(deploy_tester_contract: Callable) -> Contract:
    """Deploy a CustomToken contract with zero initial supply"""
    return deploy_tester_contract(CONTRACT_CUSTOM_TOKEN, (0, 18, "ZeroToken", "ZRO"))


@pytest.fixture()
def human_standard_token(deploy_token_contract: Callable, token_args: Dict) -> Contract:
    """Deploy HumanStandardToken contract"""
    return deploy_token_contract(
        _initialAmount=token_args["initial_supply"],
        _decimalUnits=token_args["decimal_units"],
        _tokenName=token_args["token_name"],
        _tokenSymbol=token_args["token_symbol"],
    )


@pytest.fixture
def deploy_token_contract(deploy_tester_contract: Callable) -> Callable:
    """Returns a function that deploys a generic HumanStandardToken contract"""

    def f(**args: Dict) -> Contract:
        return deploy_tester_contract(CONTRACT_HUMAN_STANDARD_TOKEN, **args)

    return f


@pytest.fixture
def standard_token_contract(custom_token: Contract) -> Contract:
    """Deployed CustomToken contract"""
    return custom_token
