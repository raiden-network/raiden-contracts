import pytest

from raiden_contracts.constants import CONTRACT_USER_DEPOSIT


@pytest.fixture
def user_deposit_contract(
    deploy_tester_contract,
    custom_token,
):
    return deploy_tester_contract(
        CONTRACT_USER_DEPOSIT,
        {},
        [custom_token.address],
    )
