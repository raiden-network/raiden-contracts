import pytest

from raiden_contracts.constants import CONTRACT_USER_DEPOSIT


@pytest.fixture
def user_deposit_contract(
    deploy_tester_contract,
    custom_token,
    monitoring_service_external,
):
    return deploy_tester_contract(
        CONTRACT_USER_DEPOSIT,
        {},
        [custom_token.address],
    )


@pytest.fixture
def udc_transfer_contract(
    deploy_tester_contract,
    user_deposit_contract,
):
    return deploy_tester_contract(
        'UDCTransfer',
        {},
        [user_deposit_contract.address],
    )
