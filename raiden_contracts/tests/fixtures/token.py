import pytest
from raiden_contracts.constants import (
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_HUMAN_STANDARD_TOKEN,
    CONTRACT_CUSTOM_TOKEN,
    CONTRACT_CUSTOM_TOKEN_NO_DECIMALS,
)
from .utils import *  # flake8: noqa

token_args = [
    (10 ** 26, 18, CONTRACT_CUSTOM_TOKEN, 'TKN')
]

token_args_7_decimals = [
    (10 ** 26, 7, CONTRACT_CUSTOM_TOKEN, 'TD6')
]

token_args_no_decimals = [
    (10 ** 26, CONTRACT_CUSTOM_TOKEN_NO_DECIMALS, 'TNO')
]


@pytest.fixture(params=token_args)
def custom_token_params(request):
    return request.param


@pytest.fixture(params=token_args_7_decimals)
def custom_token_7_decimals_params(request):
    return request.param


@pytest.fixture(params=token_args_no_decimals)
def custom_token_no_decimals_params(request):
    return request.param


@pytest.fixture()
def custom_token(deploy_tester_contract, custom_token_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN,
        [],
        custom_token_params
    )


@pytest.fixture()
def custom_token_7_decimals(deploy_tester_contract, custom_token_7_decimals_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN,
        [],
        custom_token_7_decimals_params
    )


@pytest.fixture()
def custom_token_no_decimals(deploy_tester_contract, custom_token_no_decimals_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        CONTRACT_CUSTOM_TOKEN_NO_DECIMALS,
        [],
        custom_token_no_decimals_params
    )


@pytest.fixture
def deploy_token_contract(deploy_tester_contract):
    """Returns a function that deploys a generic HumanStandardToken contract"""
    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str):
        assert initial_amount > 0
        assert decimals > 0
        return deploy_tester_contract(
            CONTRACT_HUMAN_STANDARD_TOKEN,
            [],
            [initial_amount, decimals, token_name, token_symbol]
        )

    return f



@pytest.fixture
def standard_token_contract(custom_token):
    """Deployed CustomToken contract"""
    return custom_token
