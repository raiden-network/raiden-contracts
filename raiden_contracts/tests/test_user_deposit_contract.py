import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import CONTRACTS_VERSION, UserDepositEvent


def test_deposit(
    user_deposit_contract,
    custom_token,
    get_accounts,
):
    (A, B) = get_accounts(2)
    custom_token.functions.mint(100).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 30).transact({'from': A})

    # deposit to A's own balance
    user_deposit_contract.functions.deposit(A, 10).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 90
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 10

    # increase A's deposit
    user_deposit_contract.functions.deposit(A, 20).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 20
    assert custom_token.functions.balanceOf(A).call() == 80
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 20

    # a deposit can't be decreased by calling deposit
    with pytest.raises(TransactionFailed):
        user_deposit_contract.functions.deposit(A, 19).transact({'from': A})

    # A deposits to the benefit of B
    user_deposit_contract.functions.deposit(B, 10).transact({'from': A})
    assert user_deposit_contract.functions.balances(B).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 70
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 30

    # Can't deposit more than the token contract allows
    with pytest.raises(TransactionFailed):
        user_deposit_contract.functions.deposit(A, 21).transact({'from': A})


def test_transfer(
    user_deposit_contract,
    udc_transfer_contract,
    custom_token,
    get_accounts,
    event_handler,
):
    ev_handler = event_handler(user_deposit_contract)
    (A, B) = get_accounts(2)
    custom_token.functions.mint(10).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 10).transact({'from': A})
    user_deposit_contract.functions.deposit(A, 10).transact({'from': A})

    # only trusted contracts can call transfer (init has not been called, yet)
    with pytest.raises(TransactionFailed):
        udc_transfer_contract.functions.transfer(A, B, 10).transact()

    # happy case
    user_deposit_contract.functions.init(udc_transfer_contract.address).transact()
    tx_hash = udc_transfer_contract.functions.transfer(A, B, 10).transact()
    ev_handler.assert_event(tx_hash, UserDepositEvent.BALANCE_REDUCED, dict(owner=A, newBalance=0))
    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 10

    # no tokens left
    assert not udc_transfer_contract.functions.transfer(A, B, 1).call()

    # (not) enough tokens left
    assert udc_transfer_contract.functions.transfer(B, A, 10).call()
    assert not udc_transfer_contract.functions.transfer(B, A, 11).call()


def test_withdraw(
    user_deposit_contract,
    custom_token,
    get_accounts,
    web3,
    event_handler,
):
    """ Test the interaction between planWithdraw, widthdraw and effectiveBalance
    """
    ev_handler = event_handler(user_deposit_contract)
    (A,) = get_accounts(1)
    custom_token.functions.mint(30).transact({'from': A})
    custom_token.functions.approve(user_deposit_contract.address, 30).transact({'from': A})
    user_deposit_contract.functions.deposit(A, 30).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 30

    # plan withdraw of 20 tokens
    tx_hash = user_deposit_contract.functions.planWithdraw(20).transact({'from': A})
    ev_handler.assert_event(
        tx_hash,
        UserDepositEvent.WITHDRAW_PLANNED,
        dict(withdrawer=A, plannedBalance=10),
    )
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 10

    # withdraw won't work before withdraw_delay elapsed
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    web3.testing.mine(withdraw_delay - 2)
    with pytest.raises(TransactionFailed):
        user_deposit_contract.functions.withdraw(18).transact({'from': A})

    # can't withdraw more then planned
    web3.testing.mine(1)  # now withdraw_delay is over
    with pytest.raises(TransactionFailed):
        user_deposit_contract.functions.withdraw(21).transact({'from': A})

    # actually withdraw 18 tokens
    user_deposit_contract.functions.withdraw(18).transact({'from': A})
    assert user_deposit_contract.functions.balances(A).call() == 12
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 12


def test_version(user_deposit_contract):
    """ Check the result of contract_version() call on the UserDeposit """
    version = user_deposit_contract.functions.contract_version().call()
    assert version == CONTRACTS_VERSION
