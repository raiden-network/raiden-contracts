import pytest

from raiden_contracts.constants import CONTRACT_USER_DEPOSIT
from raiden_contracts.tests.fixtures.token import CUSTOM_TOKEN_TOTAL_SUPPLY


@pytest.fixture(scope='session')
def user_deposit_whole_balance_limit():
    return CUSTOM_TOKEN_TOTAL_SUPPLY // 100


@pytest.fixture(scope='session')
def uninitialized_user_deposit_contract(
        deploy_tester_contract,
        custom_token,
        user_deposit_whole_balance_limit,
):
    return deploy_tester_contract(
        CONTRACT_USER_DEPOSIT,
        {},
        [custom_token.address, user_deposit_whole_balance_limit],
    )


@pytest.fixture
def user_deposit_contract(
        uninitialized_user_deposit_contract,
        monitoring_service_external,
        one_to_n_contract,
):
    uninitialized_user_deposit_contract.functions.init(
        monitoring_service_external.address,
        one_to_n_contract.address,
    ).call_and_transact()
    return uninitialized_user_deposit_contract


@pytest.fixture
def udc_transfer_contract(
        deploy_tester_contract,
        uninitialized_user_deposit_contract,
):
    return deploy_tester_contract(
        'UDCTransfer',
        {},
        [uninitialized_user_deposit_contract.address],
    )


@pytest.fixture
def deposit_to_udc(
        user_deposit_contract,
        custom_token,
        get_accounts,
        get_private_key,
        web3,
        event_handler,
):
    def deposit(receiver, amount):
        """ Uses UDC's monotonous deposit amount handling

        If you call it twice, only amount2 - amount1 will be deposited. More
        will be mined and approved to keep the implementation simple, though.
        """
        custom_token.functions.mint(amount).call_and_transact({'from': receiver})
        custom_token.functions.approve(
            user_deposit_contract.address,
            amount,
        ).call_and_transact({'from': receiver})
        user_deposit_contract.functions.deposit(
            receiver,
            amount,
        ).call_and_transact({'from': receiver})
    return deposit
