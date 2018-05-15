import pytest
from raiden_contracts.utils.config import C_CUSTOM_TOKEN
from .utils import *  # flake8: noqa

token_args = [
    (10 ** 26, 18, 'CustomToken', 'TKN')
]


@pytest.fixture(params=token_args)
def custom_token_params(request):
    return request.param


@pytest.fixture()
def custom_token(deploy_tester_contract, custom_token_params):
    """Deploy CustomToken contract"""
    return deploy_tester_contract(
        C_CUSTOM_TOKEN,
        [],
        custom_token_params
    )


@pytest.fixture
def deploy_token_contract(deploy_tester_contract):
    """Returns a function that deploys a generic HumanStandardToken contract"""
    def f(initial_amount: int, decimals: int, token_name: str, token_symbol: str):
        assert initial_amount > 0
        assert decimals > 0
        return deploy_tester_contract(
            'HumanStandardToken',
            [],
            [initial_amount, decimals, token_name, token_symbol]
        )

    return f



@pytest.fixture
def standard_token_contract(deploy_token_contract):
    """Deployed HumanStandardToken contract"""
    return deploy_token_contract(1000000, 10, 'TT', 'TTK')
