from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ValidationError

from raiden_contracts.constants import EMPTY_ADDRESS, TEST_SETTLE_TIMEOUT_MIN, ChannelEvent
from raiden_contracts.tests.fixtures.channel import call_settle
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    NOT_ADDRESS,
    UINT256_MAX,
    ChannelValues,
    call_and_transact,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_new_deposit


def test_deposit_channel_call(
    token_network: Contract,
    custom_token: Contract,
    create_channel: Callable,
    get_accounts: Callable,
) -> None:
    """Calling setTotalDeposit() fails with various invalid inputs"""
    (A, B) = get_accounts(2)
    deposit_A = 200
    channel_identifier = create_channel(A, B)[0]

    call_and_transact(custom_token.functions.mint(deposit_A), {"from": A})

    call_and_transact(
        custom_token.functions.approve(token_network.address, deposit_A), {"from": A}
    )

    # Validation failure with an invalid channel identifier
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(-1, A, deposit_A, B)
    # Validation failure with the empty string instead of a channel identifier
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit("", A, deposit_A, B)
    # Validation failure with a negative number instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, -1, A, deposit_A)
    # Validation failure with an empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, "", deposit_A, B)
    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, NOT_ADDRESS, deposit_A, B)
    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, 0x0, deposit_A, B)
    # Validation failure with the empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, "")
    # Validation failure with an odd-length string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, NOT_ADDRESS)
    # Validation failure with the number zero instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, 0x0)
    # Validation failure with a negative amount of deposit
    with pytest.raises(ValidationError):
        token_network.functions.setTotalDeposit(channel_identifier, A, -1, B)
    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed, match="TN: participant address zero"):
        token_network.functions.setTotalDeposit(
            channel_identifier, EMPTY_ADDRESS, deposit_A, B
        ).call({"from": A})
    # Transaction failure with the zero address
    with pytest.raises(TransactionFailed, match="TN: partner address zero"):
        token_network.functions.setTotalDeposit(
            channel_identifier, A, deposit_A, EMPTY_ADDRESS
        ).call({"from": A})
    # Transaction failure with zero total deposit
    with pytest.raises(TransactionFailed, match="TN/deposit: total_deposit is zero"):
        token_network.functions.setTotalDeposit(channel_identifier, A, 0, B).call({"from": A})

    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, B),
        {"from": A},
    )
    assert (
        deposit_A
        == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )
    assert (
        0 == token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()[0]
    )


def test_deposit_notapproved(
    token_network: Contract,
    custom_token: Contract,
    create_channel: Callable,
    get_accounts: Callable,
    web3: Web3,
) -> None:
    """Calling setTotalDeposit() fails without approving transfers on the token contract"""
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    deposit_A = 1

    call_and_transact(custom_token.functions.mint(deposit_A), {"from": A})
    mine_blocks(web3, 1)
    balance = custom_token.functions.balanceOf(A).call()
    assert balance >= deposit_A, f"minted {deposit_A} but the balance is still {balance}"

    with pytest.raises(TransactionFailed):  # TODO: why doesn"t this throw an error on transfer?
        token_network.functions.setTotalDeposit(channel_identifier, A, deposit_A, B).call(
            {"from": A}
        )
    assert (
        0 == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )


def test_null_or_negative_deposit_fail(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    assign_tokens: Callable,
    get_accounts: Callable,
) -> None:
    """setTotalDeposit() fails when the total deposit does not increase"""
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 2, B)

    assign_tokens(A, 1)

    # setTotalDeposit is idempotent
    with pytest.raises(TransactionFailed, match="TN/deposit: no deposit added"):
        token_network.functions.setTotalDeposit(channel_identifier, A, 2, B).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/deposit: deposit underflow"):
        token_network.functions.setTotalDeposit(channel_identifier, A, 1, B).call({"from": A})
    assert (
        2 == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )


def test_deposit_delegate_works(
    get_accounts: Callable,
    create_channel: Callable,
    channel_deposit: Callable,
    token_network: Contract,
) -> None:
    """A third party can successfully call setTokenDeposit()"""
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 2, B, tx_from=C)
    assert (
        2 == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )


def test_deposit_wrong_channel(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    assign_tokens: Callable,
) -> None:
    """setTotalDeposit() with a wrong channelID fails"""
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_identifier2 = create_channel(A, C)[0]
    assign_tokens(A, 10)

    with pytest.raises(TransactionFailed, match="TN/deposit: channel id mismatch"):
        token_network.functions.setTotalDeposit(channel_identifier2, A, 10, B).call({"from": A})
    with pytest.raises(TransactionFailed, match="TN/deposit: channel id mismatch"):
        token_network.functions.setTotalDeposit(channel_identifier, A, 10, C).call({"from": A})

    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, A, 10, B),
        {"from": A},
    )
    assert (
        10 == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )


@pytest.mark.skip("Not necessary with limited deposits for the test release.")
def test_channel_deposit_overflow(
    get_accounts: Callable, create_channel: Callable, channel_deposit: Callable
) -> None:
    (A, B) = get_accounts(2)
    deposit_A = 50
    deposit_B_ok = UINT256_MAX - deposit_A
    deposit_B_fail = deposit_B_ok + 1

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    with pytest.raises(TransactionFailed, match="TN/deposit: deposit overflow"):
        channel_deposit(channel_identifier, B, deposit_B_fail, A)

    channel_deposit(channel_identifier, B, deposit_B_ok, A)


def test_deposit_channel_state(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
) -> None:
    """Observe how setTotalDeposit() changes the results of getChannelParticipantInfo()"""
    (A, B) = get_accounts(2)
    A_planned_deposit = 10
    B_planned_deposit = 15

    channel_identifier = create_channel(A, B)[0]

    A_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, A, B
    ).call()[0]
    assert A_onchain_deposit == 0

    B_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, B, A
    ).call()[0]
    assert B_onchain_deposit == 0

    channel_deposit(channel_identifier, A, A_planned_deposit, B)
    A_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, A, B
    ).call()[0]
    assert A_onchain_deposit == A_planned_deposit
    B_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, B, A
    ).call()[0]
    assert B_onchain_deposit == 0

    channel_deposit(channel_identifier, B, B_planned_deposit, A)
    A_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, A, B
    ).call()[0]
    assert A_onchain_deposit == A_planned_deposit
    B_onchain_deposit = token_network.functions.getChannelParticipantInfo(
        channel_identifier, B, A
    ).call()[0]
    assert B_onchain_deposit == B_planned_deposit


def test_deposit_wrong_state_fail(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    assign_tokens: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """setTotalDeposit() fails on Closed or Settled channels."""
    (A, B) = get_accounts(2)
    vals_A = ChannelValues(deposit=2, transferred=0)
    vals_B = ChannelValues(deposit=2, transferred=0)
    channel_identifier = create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)[0]
    assign_tokens(A, vals_A.deposit)
    assign_tokens(B, vals_B.deposit)
    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, A, vals_A.deposit, B),
        {"from": A},
    )
    call_and_transact(
        token_network.functions.setTotalDeposit(channel_identifier, B, vals_B.deposit, A),
        {"from": B},
    )
    assert (
        vals_A.deposit
        == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )
    assert (
        vals_B.deposit
        == token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()[0]
    )

    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)

    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier,
            non_closing_participant=B,
            closing_participant=A,
            balance_hash=EMPTY_BALANCE_HASH,
            nonce=0,
            additional_hash=EMPTY_ADDITIONAL_HASH,
            non_closing_signature=EMPTY_SIGNATURE,
            closing_signature=closing_sig,
        ),
        {"from": A},
    )

    assign_tokens(A, 10)
    assign_tokens(B, 10)
    vals_A.deposit += 5
    vals_B.deposit += 5
    with pytest.raises(TransactionFailed, match="TN: channel not open"):
        token_network.functions.setTotalDeposit(channel_identifier, A, vals_A.deposit, B).call(
            {"from": A}
        )
    with pytest.raises(TransactionFailed, match="TN: channel not open"):
        token_network.functions.setTotalDeposit(channel_identifier, B, vals_B.deposit, A).call(
            {"from": B}
        )

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_settle(token_network, channel_identifier, A, vals_A, B, vals_B)
    with pytest.raises(TransactionFailed, match="TN: channel not open"):
        token_network.functions.setTotalDeposit(channel_identifier, A, vals_A.deposit, B).call(
            {"from": A}
        )
    with pytest.raises(TransactionFailed, match="TN: channel not open"):
        token_network.functions.setTotalDeposit(channel_identifier, B, vals_B.deposit, A).call(
            {"from": B}
        )


def test_deposit_channel_event(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    event_handler: Callable,
) -> None:
    """setTotalDeposit() from each participant causes a DEPOSIT event"""
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 15

    channel_identifier = create_channel(A, B)[0]

    txn_hash = channel_deposit(channel_identifier, A, deposit_A, B)
    assert (
        deposit_A
        == token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()[0]
    )

    ev_handler.add(
        txn_hash,
        ChannelEvent.DEPOSIT,
        check_new_deposit(channel_identifier, A, deposit_A),
    )

    txn_hash = channel_deposit(channel_identifier, B, deposit_B, A)
    ev_handler.add(
        txn_hash,
        ChannelEvent.DEPOSIT,
        check_new_deposit(channel_identifier, B, deposit_B),
    )

    ev_handler.check()
