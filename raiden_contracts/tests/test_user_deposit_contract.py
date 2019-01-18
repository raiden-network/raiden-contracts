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


def test_deposit(
    user_deposit_contract,
    custom_token,
    get_accounts,
):
    (A, B) = get_accounts(2)
    custom_token.functions.mint(30).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 30).transact({'from': A})

    # deposit to A's own balance
    user_deposit_contract.functions.deposit(A, 10).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 10

    # increase A's deposit
    user_deposit_contract.functions.deposit(A, 20).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 20

    # A deposits to the benefit of B
    user_deposit_contract.functions.deposit(B, 10).transact({'from': A})
    assert user_deposit_contract.functions.balances(B).call() == 10


def test_transfer(
    user_deposit_contract,
    custom_token,
    get_accounts,
):
    (A, B) = get_accounts(2)
    custom_token.functions.mint(10).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 10).transact({'from': A})
    user_deposit_contract.functions.deposit(A, 10).transact({'from': A})
    user_deposit_contract.functions.transfer(A, B, 10).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 10


def test_withdraw(
    user_deposit_contract,
    custom_token,
    get_accounts,
    web3,
):
    """ Test the interaction between planWithdraw, widthdraw and effectiveBalance
    """
    (A,) = get_accounts(1)
    custom_token.functions.mint(30).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 30).transact({'from': A})
    user_deposit_contract.functions.deposit(A, 30).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 30

    # plan withdraw of 20 tokens
    user_deposit_contract.functions.planWithdraw(20).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 10

    # actually withdraw 18 tokens
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    web3.testing.mine(withdraw_delay)
    user_deposit_contract.functions.withdraw(18).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 12
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 12
