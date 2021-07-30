from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3.contract import Contract
from web3.exceptions import ValidationError

from raiden_contracts.constants import EMPTY_ADDRESS, ChannelEvent
from raiden_contracts.tests.utils import EMPTY_LOCKSROOT, call_and_transact
from raiden_contracts.utils.events import check_channel_settled, check_withdraw_2
from raiden_contracts.utils.type_aliases import BlockExpiration

EXPIRATION = BlockExpiration(100)


def test_cooperative_settle_channel_call(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 5
    balance_B = 25

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    # negative balances
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, -1, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, -1, EXPIRATION, signature_B2, signature_A2),
        )
    # wrong participant addresses
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (0x0, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (0x0, balance_B, EXPIRATION, signature_B2, signature_A2),
        )
    # invalid signatures
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, 0x0, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, 0x0),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, 0x0, signature_A2),
        )
    with pytest.raises(ValidationError):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, 0x0),
        )
    # empty addresses
    with pytest.raises(TransactionFailed, match="TN: participant address zero"):
        call_and_transact(
            token_network.functions.cooperativeSettle(
                channel_identifier,
                (EMPTY_ADDRESS, balance_A, EXPIRATION, signature_A1, signature_B1),
                (B, balance_B, EXPIRATION, signature_B2, signature_A2),
            ),
            {"from": C},
        )
    with pytest.raises(TransactionFailed, match="TN: partner address zero"):
        call_and_transact(
            token_network.functions.cooperativeSettle(
                channel_identifier,
                (A, balance_A, EXPIRATION, signature_A1, signature_B1),
                (EMPTY_ADDRESS, balance_B, EXPIRATION, signature_B2, signature_A2),
            ),
            {"from": C},
        )

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )


def test_cooperative_settle_channel_signatures(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 4
    balance_B = 26

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1, signature_C1) = create_withdraw_signatures(
        [A, B, C], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2, signature_C2) = create_withdraw_signatures(
        [A, B, C], channel_identifier, B, balance_B, EXPIRATION
    )

    with pytest.raises(TransactionFailed, match="TN/withdraw: invalid participant sig"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_C1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ).call({"from": C})
    with pytest.raises(TransactionFailed, match="TN/withdraw: channel id mismatch"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_C1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ).call({"from": C})
    with pytest.raises(TransactionFailed, match="TN/withdraw: invalid participant sig"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_C2, signature_A2),
        ).call({"from": C})
    with pytest.raises(TransactionFailed, match="TN/withdraw: channel id mismatch"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_C2),
        ).call({"from": C})

    with pytest.raises(TransactionFailed, match="TN/withdraw: invalid participant sig"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_B, EXPIRATION, signature_A1, signature_B1),
            (B, balance_A, EXPIRATION, signature_B2, signature_A2),
        ).call({"from": C})

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )


def test_cooperative_settle_channel_0(
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    cooperative_settle_state_tests: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 0
    balance_B = 30

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


def test_cooperative_settle_channel_00(
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    cooperative_settle_state_tests: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 0
    deposit_B = 0
    balance_A = 0
    balance_B = 0

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


def test_cooperative_settle_channel_state(
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    cooperative_settle_state_tests: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 5
    balance_B = 25
    assert deposit_A + deposit_B == balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


def test_cooperative_settle_channel_state_withdraw(
    custom_token: Contract,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    cooperative_settle_state_tests: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 3
    withdraw_B = 7
    balance_A = 5
    balance_B = 15
    assert deposit_A + deposit_B == withdraw_A + withdraw_B + balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    withdraw_channel(channel_identifier, A, withdraw_A, EXPIRATION, B)
    withdraw_channel(channel_identifier, B, withdraw_B, EXPIRATION, A)

    # We need to add the already withdrawn amount to the balance as `withdraw_amount`
    # is a monotonic value
    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A + withdraw_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B + withdraw_B, EXPIRATION
    )

    pre_account_balance_A = custom_token.functions.balanceOf(A).call()
    pre_account_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A + withdraw_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B + withdraw_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )

    cooperative_settle_state_tests(
        channel_identifier,
        A,
        balance_A,
        B,
        balance_B,
        pre_account_balance_A,
        pre_account_balance_B,
        pre_balance_contract,
    )


def test_cooperative_settle_channel_smaller_total_amount(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 15 - 1
    balance_B = 15

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    with pytest.raises(TransactionFailed, match="TN/coopSettle: incomplete amount"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ).call({"from": C})


def test_cooperative_settle_channel_bigger_withdraw(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 3
    withdraw_B = 7
    balance_A = 6
    balance_B = 15
    assert deposit_A + deposit_B < withdraw_A + withdraw_B + balance_A + balance_B

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    withdraw_channel(channel_identifier, A, withdraw_A, EXPIRATION, B)
    withdraw_channel(channel_identifier, B, withdraw_B, EXPIRATION, A)

    # We need to add the already withdrawn amount to the balance as `withdraw_amount`
    # is a monotonic value
    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A + withdraw_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B + withdraw_B, EXPIRATION
    )

    with pytest.raises(TransactionFailed, match="TN/coopSettle: incomplete amount"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A + withdraw_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B + withdraw_B, EXPIRATION, signature_B2, signature_A2),
        ).call({"from": C})


def test_cooperative_settle_channel_wrong_balances(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    balance_A = 7
    balance_B = 23

    balance_A_fail1 = 20
    balance_B_fail1 = 11
    balance_A_fail2 = 6
    balance_B_fail2 = 8

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A1_fail1, signature_B1_fail1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A_fail1, EXPIRATION
    )
    (signature_A2_fail1, signature_B2_fail1) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B_fail1, EXPIRATION
    )

    with pytest.raises(TransactionFailed, match="TN/coopSettle: incomplete amount"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A_fail1, EXPIRATION, signature_A1_fail1, signature_B1_fail1),
            (B, balance_B_fail1, EXPIRATION, signature_B2_fail1, signature_A2_fail1),
        ).call({"from": C})

    (signature_A1_fail2, signature_B1_fail2) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A_fail2, EXPIRATION
    )
    (signature_A2_fail2, signature_B2_fail2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B_fail2, EXPIRATION
    )

    with pytest.raises(TransactionFailed, match="TN/coopSettle: incomplete amount"):
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A_fail1, EXPIRATION, signature_A1_fail2, signature_B1_fail2),
            (B, balance_B_fail1, EXPIRATION, signature_B2_fail2, signature_A2_fail2),
        ).call({"from": C})

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )
    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
        ),
        {"from": C},
    )


def test_cooperative_close_replay_reopened_channel(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B) = get_accounts(2)
    deposit_A = 15
    deposit_B = 10
    balance_A = 2
    balance_B = 23

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, A, deposit_A, B)
    channel_deposit(channel_identifier1, B, deposit_B, A)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier1, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier1, B, balance_B, EXPIRATION
    )

    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier1,
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
        ),
        {"from": B},
    )

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, A, deposit_A, B)
    channel_deposit(channel_identifier2, B, deposit_B, A)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed, match="TN/withdraw: invalid participant sig"):
        token_network.functions.cooperativeSettle(
            channel_identifier2,
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
        ).call({"from": B})

    # Signed message with the correct channel identifier must work
    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier2, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier2, B, balance_B, EXPIRATION
    )
    call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier2,
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
        ),
        {"from": B},
    )


def test_cooperative_settle_channel_event(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_withdraw_signatures: Callable,
    event_handler: Callable,
) -> None:
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    balance_A = 2
    balance_B = 8

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    (signature_A1, signature_B1) = create_withdraw_signatures(
        [A, B], channel_identifier, A, balance_A, EXPIRATION
    )
    (signature_A2, signature_B2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, balance_B, EXPIRATION
    )

    txn_hash = call_and_transact(
        token_network.functions.cooperativeSettle(
            channel_identifier,
            (B, balance_B, EXPIRATION, signature_B2, signature_A2),
            (A, balance_A, EXPIRATION, signature_A1, signature_B1),
        ),
        {"from": B},
    )

    withdraw_events = token_network.events.ChannelWithdraw.getLogs()
    assert any(map(check_withdraw_2(channel_identifier, A, balance_A), withdraw_events))
    assert any(map(check_withdraw_2(channel_identifier, B, balance_B), withdraw_events))

    ev_handler.add(
        txn_hash,
        ChannelEvent.SETTLED,
        check_channel_settled(
            channel_identifier,
            B,
            balance_B,
            EMPTY_LOCKSROOT,
            A,
            balance_A,
            EMPTY_LOCKSROOT,
        ),
    )
    ev_handler.check()
