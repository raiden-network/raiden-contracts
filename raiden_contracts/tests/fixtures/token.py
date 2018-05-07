import pytest
from raiden_contracts.utils.config import C_CUSTOM_TOKEN
from .utils import *  # flake8: noqa

token_args = [
    (10 ** 26, 18, 'CustomToken', 'TKN'),
    # (10 ** 26, 0, 'CustomToken', 'TKN')
]


@pytest.fixture(params=token_args)
def token_params(request):
    return request.param


@pytest.fixture()
def custom_token(deploy_tester_contract, token_params):
    return deploy_tester_contract(
        C_CUSTOM_TOKEN,
        [],
        token_params
    )
