import pytest
from raiden_contracts.utils.config import C_HUMAN_STANDARD_TOKEN, C_CUSTOM_TOKEN

token_args = [
    (10 ** 26, 18, 'CustomToken', 'TKN'),
    (10 ** 26, 0, 'CustomToken', 'TKN')
]


@pytest.fixture(params=token_args)
def token_params(request):
    return request.param


@pytest.fixture()
def get_human_token(chain, create_contract):
    def get(arguments, transaction=None):
        HumanToken = chain.provider.get_contract_factory(C_HUMAN_STANDARD_TOKEN)
        token_contract = create_contract(HumanToken, arguments, transaction)
        return token_contract
    return get


@pytest.fixture()
def get_custom_token(chain, create_contract):
    def get(arguments, transaction=None):
        CustomToken = chain.provider.get_contract_factory(C_CUSTOM_TOKEN)
        token_contract = create_contract(CustomToken, arguments, transaction)
        return token_contract
    return get


@pytest.fixture()
def custom_token(get_custom_token, token_params):
    return get_custom_token(token_params)
