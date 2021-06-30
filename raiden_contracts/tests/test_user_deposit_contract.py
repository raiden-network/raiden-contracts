from typing import Callable, Tuple

import pytest
from eth.constants import ZERO_ADDRESS
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract

from raiden_contracts.constants import UserDepositEvent
from raiden_contracts.tests.utils import call_and_transact
from raiden_contracts.tests.utils.blockchain import mine_blocks


def test_deposit(
    user_deposit_contract: Contract, custom_token: Contract, get_accounts: Callable[[int], Tuple]
) -> None:
    (A, B) = get_accounts(2)
    call_and_transact(custom_token.functions.mint(100), {"from": A})
    call_and_transact(
        custom_token.functions.approve(user_deposit_contract.address, 30), {"from": A}
    )

    # deposit to A's own balance
    call_and_transact(user_deposit_contract.functions.deposit(A, 10), {"from": A})
    assert user_deposit_contract.functions.balances(A).call() == 10
    assert user_deposit_contract.functions.total_deposit(A).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 90
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 10

    # increase A's deposit
    call_and_transact(user_deposit_contract.functions.deposit(A, 20), {"from": A})
    assert user_deposit_contract.functions.balances(A).call() == 20
    assert user_deposit_contract.functions.total_deposit(A).call() == 20
    assert custom_token.functions.balanceOf(A).call() == 80
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 20

    # a deposit can't be decreased by calling deposit
    with pytest.raises(TransactionFailed, match="deposit not increasing"):
        user_deposit_contract.functions.deposit(A, 19).call({"from": A})

    # A deposits to the benefit of B
    call_and_transact(user_deposit_contract.functions.deposit(B, 10), {"from": A})
    assert user_deposit_contract.functions.balances(B).call() == 10
    assert user_deposit_contract.functions.total_deposit(B).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 70
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 30

    # Can't deposit more than the token contract allows
    with pytest.raises(TransactionFailed):
        user_deposit_contract.functions.deposit(A, 21).call({"from": A})

    # Can't deposit more than the whole_balance_limit
    limit = user_deposit_contract.functions.whole_balance_limit().call()
    assert limit > 0
    call_and_transact(custom_token.functions.mint(limit + 1), {"from": A})
    call_and_transact(
        custom_token.functions.approve(user_deposit_contract.address, limit + 1),
        {"from": A},
    )
    with pytest.raises(TransactionFailed, match="too much deposit"):
        user_deposit_contract.functions.deposit(A, limit + 1).call({"from": A})


def test_transfer(
    uninitialized_user_deposit_contract: Contract,
    udc_transfer_contract: Contract,
    get_accounts: Callable[[int], Tuple],
    event_handler: Callable,
    custom_token: Contract,
) -> None:
    user_deposit_contract = uninitialized_user_deposit_contract
    ev_handler = event_handler(user_deposit_contract)
    (A, B) = get_accounts(2)
    call_and_transact(custom_token.functions.mint(10), {"from": A})
    call_and_transact(
        custom_token.functions.approve(user_deposit_contract.address, 10), {"from": A}
    )
    call_and_transact(user_deposit_contract.functions.deposit(A, 10), {"from": A})

    # only trusted contracts can call transfer (init has not been called, yet)
    with pytest.raises(TransactionFailed, match="unknown caller"):
        udc_transfer_contract.functions.transfer(A, B, 10).call()

    # happy case
    call_and_transact(
        user_deposit_contract.functions.init(
            udc_transfer_contract.address, udc_transfer_contract.address
        )
    )
    tx_hash = call_and_transact(udc_transfer_contract.functions.transfer(A, B, 10))
    ev_handler.assert_event(tx_hash, UserDepositEvent.BALANCE_REDUCED, dict(owner=A, newBalance=0))
    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.balances(B).call() == 10

    # no tokens left
    assert not udc_transfer_contract.functions.transfer(A, B, 1).call()

    # (not) enough tokens left
    assert udc_transfer_contract.functions.transfer(B, A, 10).call()
    assert not udc_transfer_contract.functions.transfer(B, A, 11).call()


def test_deposit_after_transfer(
    uninitialized_user_deposit_contract: Contract,
    udc_transfer_contract: Contract,
    custom_token: Contract,
    get_accounts: Callable[[int], Tuple],
) -> None:
    """Make sure that `total_deposit` and `balance` are not mixed up.

    When doing a deposit followed by a transfer, both variables start to differ
    and we can use another deposit to verify that each is handled correctly.
    """
    user_deposit_contract = uninitialized_user_deposit_contract
    call_and_transact(
        user_deposit_contract.functions.init(
            udc_transfer_contract.address, udc_transfer_contract.address
        )
    )
    (A, B) = get_accounts(2)
    call_and_transact(custom_token.functions.mint(100), {"from": A})
    call_and_transact(
        custom_token.functions.approve(user_deposit_contract.address, 30), {"from": A}
    )

    # deposit + transact
    call_and_transact(user_deposit_contract.functions.deposit(A, 10), {"from": A})
    call_and_transact(udc_transfer_contract.functions.transfer(A, B, 10))
    assert user_deposit_contract.functions.balances(A).call() == 0
    assert user_deposit_contract.functions.total_deposit(A).call() == 10
    assert custom_token.functions.balanceOf(A).call() == 90
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 10

    # check after another deposit
    call_and_transact(user_deposit_contract.functions.deposit(A, 20), {"from": A})
    assert user_deposit_contract.functions.balances(A).call() == 10
    assert user_deposit_contract.functions.total_deposit(A).call() == 20
    assert custom_token.functions.balanceOf(A).call() == 80
    assert custom_token.functions.balanceOf(user_deposit_contract.address).call() == 20


def test_withdraw(
    user_deposit_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    web3: Web3,
    event_handler: Callable,
) -> None:
    """Test the interaction between planWithdraw, withdraw and effectiveBalance"""
    ev_handler = event_handler(user_deposit_contract)
    (A,) = get_accounts(1)
    deposit_to_udc(A, 30)
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 30

    # plan withdraw of 20 tokens
    tx_hash = call_and_transact(user_deposit_contract.functions.planWithdraw(20), {"from": A})
    ev_handler.assert_event(
        tx_hash,
        UserDepositEvent.WITHDRAW_PLANNED,
        dict(withdrawer=A, plannedBalance=10),
    )
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 10

    # withdraw won't work before withdraw_delay elapsed
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    mine_blocks(web3, withdraw_delay - 1)
    with pytest.raises(TransactionFailed, match="withdrawing too early"):
        user_deposit_contract.functions.withdraw(18).call({"from": A})

    # can't withdraw more then planned
    mine_blocks(web3, 1)  # now withdraw_delay is over
    with pytest.raises(TransactionFailed, match="withdrawing more than planned"):
        user_deposit_contract.functions.withdraw(21).call({"from": A})

    # actually withdraw 18 tokens
    call_and_transact(user_deposit_contract.functions.withdraw(18), {"from": A})
    assert user_deposit_contract.functions.balances(A).call() == 12
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 12


def test_withdraw_to_beneficiary(
    user_deposit_contract: Contract,
    deposit_to_udc: Callable,
    get_accounts: Callable,
    web3: Web3,
    event_handler: Callable,
    custom_token: Contract,
) -> None:
    """Test the interaction between planWithdraw, withdrawToBeneficiary and effectiveBalance"""
    ev_handler = event_handler(user_deposit_contract)
    (A, B) = get_accounts(2)
    deposit_to_udc(A, 30)
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 30

    # plan withdraw of 20 tokens
    tx_hash = call_and_transact(user_deposit_contract.functions.planWithdraw(20), {"from": A})
    ev_handler.assert_event(
        tx_hash,
        UserDepositEvent.WITHDRAW_PLANNED,
        dict(withdrawer=A, plannedBalance=10),
    )
    assert user_deposit_contract.functions.balances(A).call() == 30
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 10

    # beneficiary can not be zero address
    with pytest.raises(TransactionFailed, match="beneficiary is zero"):
        user_deposit_contract.functions.withdrawToBeneficiary(18, ZERO_ADDRESS).call({"from": A})

    # withdraw won't work before withdraw_delay elapsed
    withdraw_delay = user_deposit_contract.functions.withdraw_delay().call()
    mine_blocks(web3, withdraw_delay - 1)
    with pytest.raises(TransactionFailed, match="withdrawing too early"):
        user_deposit_contract.functions.withdrawToBeneficiary(18, B).call({"from": A})

    # can't withdraw more then planned
    mine_blocks(web3, 1)  # now withdraw_delay is over
    with pytest.raises(TransactionFailed, match="withdrawing more than planned"):
        user_deposit_contract.functions.withdrawToBeneficiary(21, B).call({"from": A})

    # actually withdraw 18 tokens
    assert custom_token.functions.balanceOf(B).call() == 0
    call_and_transact(user_deposit_contract.functions.withdrawToBeneficiary(18, B), {"from": A})
    assert user_deposit_contract.functions.balances(A).call() == 12
    assert user_deposit_contract.functions.effectiveBalance(A).call() == 12

    assert custom_token.functions.balanceOf(B).call() == 18
