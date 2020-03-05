from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ValidationError

from raiden_contracts.constants import (
    EMPTY_ADDRESS,
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
)
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    LOCKSROOT_OF_NO_LOCKS,
    UINT256_MAX,
    call_and_transact,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_withdraw


def test_withdraw_call(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    """ setTotalWithdraw() fails with various wrong arguments """
    (A, B) = get_accounts(2)
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B], channel_identifier, A, withdraw_A, UINT256_MAX
    )

    # Failure with zero (integer) instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=0x0,
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        )

    # Failure with the empty string instead of an address
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant="",
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        )

    # Failure with a negative number as the total withdrawn amount
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=-1,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        )

    # Failure with an overflown number as the total withdrawn amount
    with pytest.raises(ValidationError):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=UINT256_MAX + 1,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        )

    # Failure with the zero address insted of a participant's address
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=EMPTY_ADDRESS,
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        ).call({"from": A})

    # Failure with zero as the total withdrawn amount
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=0,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        ).call({"from": A})

    # Failure with the empty signature instead of A's
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=EMPTY_SIGNATURE,
            partner_signature=signature_B_for_A,
        ).call({"from": A})

    # Failure with the empty signature instead of B's
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=EMPTY_SIGNATURE,
        ).call({"from": A})

    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=withdraw_A,
            expiration_block=UINT256_MAX,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        ),
        {"from": A},
    )


def test_withdraw_call_near_expiration(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    web3: Web3,
) -> None:
    """ setTotalWithdraw() succeeds when expiration_block is one block in the future """
    (A, B) = get_accounts(2)
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, 10, 1)
    expiration = web3.eth.blockNumber + 1

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B], channel_identifier, A, withdraw_A, expiration
    )

    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier=channel_identifier,
            participant=A,
            total_withdraw=withdraw_A,
            expiration_block=expiration,
            participant_signature=signature_A_for_A,
            partner_signature=signature_B_for_A,
        ),
        {"from": A},
    )


def test_withdraw_wrong_state(
    web3: Web3,
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    withdraw_channel: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ setTotalWithdraw() should fail on a closed or settled channel """
    (A, B) = get_accounts(2)
    withdraw_A = 1

    assert token_network.functions.getChannelIdentifier(A, B).call() == 0

    channel_identifier = create_channel_and_deposit(A, B, 10, 14, TEST_SETTLE_TIMEOUT_MIN)
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.OPENED

    # Channel is open, withdraw must work
    withdraw_channel(channel_identifier, A, withdraw_A, UINT256_MAX, B)

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
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.CLOSED

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, withdraw_A, UINT256_MAX, B)

    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier, A, 0, 0, LOCKSROOT_OF_NO_LOCKS, B, 0, 0, LOCKSROOT_OF_NO_LOCKS
        ),
        {"from": A},
    )
    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.REMOVED

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, withdraw_A, UINT256_MAX, B)


def test_withdraw_bigger(
    create_channel_and_deposit: Callable, get_accounts: Callable, withdraw_channel: Callable
) -> None:
    (A, B) = get_accounts(2)
    deposit_A = 15
    deposit_B = 13

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, deposit_A + deposit_B + 1, UINT256_MAX, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, B, deposit_A + deposit_B + 1, UINT256_MAX, A)

    withdraw_channel(channel_identifier, A, 3, UINT256_MAX, B)
    withdraw_channel(channel_identifier, B, 6, UINT256_MAX, A)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, A, deposit_A + deposit_B - 5, UINT256_MAX, B)
    with pytest.raises(TransactionFailed):
        withdraw_channel(channel_identifier, B, deposit_A + deposit_B - 2, UINT256_MAX, A)

    withdraw_channel(channel_identifier, A, deposit_A + deposit_B - 7, UINT256_MAX, B)


def test_withdraw_wrong_signers(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 5
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    (signature_A_for_A, signature_B_for_A, signature_C_for_A) = create_withdraw_signatures(
        [A, B, C], channel_identifier, A, withdraw_A, UINT256_MAX
    )
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier, A, withdraw_A, UINT256_MAX, signature_C_for_A, signature_B_for_A
        ).call({"from": C})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier, A, withdraw_A, UINT256_MAX, signature_A_for_A, signature_C_for_A
        ).call({"from": C})

    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier, A, withdraw_A, UINT256_MAX, signature_A_for_A, signature_B_for_A
        ),
        {"from": C},
    )


def test_withdraw_wrong_signature_content(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    web3: Web3,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 15
    deposit_B = 13
    withdraw_A = 3
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)
    channel_identifier_fake = token_network.functions.getChannelIdentifier(A, C).call()

    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B], channel_identifier, A, withdraw_A, UINT256_MAX
    )
    (signature_A_for_A_fake1, signature_B_for_A_fake1) = create_withdraw_signatures(
        [A, B], channel_identifier_fake, A, withdraw_A, UINT256_MAX
    )
    (signature_A_for_A_fake2, signature_B_for_A_fake2) = create_withdraw_signatures(
        [A, B], channel_identifier, B, withdraw_A, UINT256_MAX
    )
    (signature_A_for_A_fake3, signature_B_for_A_fake3) = create_withdraw_signatures(
        [A, B], channel_identifier, A, withdraw_A - 1, UINT256_MAX
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A_fake1,
            signature_B_for_A,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A,
            signature_B_for_A_fake1,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A_fake2,
            signature_B_for_A,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A,
            signature_B_for_A_fake2,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A_fake3,
            signature_B_for_A,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier,
            A,
            withdraw_A,
            UINT256_MAX,
            signature_A_for_A,
            signature_B_for_A_fake3,
        ).call({"from": A})
    with pytest.raises(TransactionFailed):
        call_and_transact(
            token_network.functions.setTotalWithdraw(
                channel_identifier, A, withdraw_A, 0, signature_A_for_A, signature_B_for_A
            ),
            {"from": A},
        )
    with pytest.raises(TransactionFailed):
        call_and_transact(
            token_network.functions.setTotalWithdraw(
                channel_identifier,
                A,
                withdraw_A,
                web3.eth.blockNumber,
                signature_A_for_A,
                signature_B_for_A,
            ),
            {"from": A},
        )

    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier, A, withdraw_A, UINT256_MAX, signature_A_for_A, signature_B_for_A
        ),
        {"from": A},
    )


def test_withdraw_channel_state(
    get_accounts: Callable,
    token_network: Contract,
    custom_token: Contract,
    create_channel_and_deposit: Callable,
    withdraw_channel: Callable,
    withdraw_state_tests: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    deposit_A = 20
    deposit_B = 10
    withdraw_A = 15
    withdraw_B = 2

    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    (_, withdrawn_amount, _, _, _, _, _) = token_network.functions.getChannelParticipantInfo(
        channel_identifier, A, B
    ).call()
    assert withdrawn_amount == 0

    withdraw_channel(channel_identifier, A, withdraw_A, UINT256_MAX, B, C)

    withdraw_state_tests(
        channel_identifier,
        A,
        deposit_A,
        withdraw_A,
        0,
        balance_A,
        B,
        deposit_B,
        0,
        balance_B,
        balance_contract,
        C,
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    withdraw_channel(channel_identifier, B, withdraw_B, UINT256_MAX, A)

    withdraw_state_tests(
        channel_identifier,
        B,
        deposit_B,
        withdraw_B,
        0,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract,
    )

    balance_A = custom_token.functions.balanceOf(A).call()
    balance_B = custom_token.functions.balanceOf(B).call()
    balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    withdraw_channel(channel_identifier, B, withdraw_B + 3, UINT256_MAX, A)

    withdraw_state_tests(
        channel_identifier,
        B,
        deposit_B,
        withdraw_B + 3,
        withdraw_B,
        balance_B,
        A,
        deposit_A,
        withdraw_A,
        balance_A,
        balance_contract,
    )


def test_withdraw_replay_reopened_channel(
    web3: Web3,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_withdraw_signatures: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    (A, B) = get_accounts(2)
    deposit_A = 20
    withdraw_A = 5

    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, A, deposit_A, B)
    (signature_A_for_A, signature_B_for_A) = create_withdraw_signatures(
        [A, B], channel_identifier1, A, withdraw_A, UINT256_MAX
    )
    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier1, A, withdraw_A, UINT256_MAX, signature_A_for_A, signature_B_for_A
        ),
        {"from": A},
    )

    closing_sig = create_close_signature_for_no_balance_proof(B, channel_identifier1)
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier1,
            non_closing_participant=A,
            closing_participant=B,
            balance_hash=EMPTY_BALANCE_HASH,
            nonce=0,
            additional_hash=EMPTY_ADDITIONAL_HASH,
            non_closing_signature=EMPTY_SIGNATURE,
            closing_signature=closing_sig,
        ),
        {"from": B},
    )
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier1, A, 0, 0, LOCKSROOT_OF_NO_LOCKS, B, 0, 0, LOCKSROOT_OF_NO_LOCKS
        ),
        {"from": A},
    )

    # Reopen the channel and make sure we cannot use the old withdraw proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, A, deposit_A, B)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.setTotalWithdraw(
            channel_identifier2, A, withdraw_A, UINT256_MAX, signature_A_for_A, signature_B_for_A
        ).call({"from": A})

    # Signed message with correct channel_identifier must work
    (signature_A_for_A2, signature_B_for_A2) = create_withdraw_signatures(
        [A, B], channel_identifier2, A, withdraw_A, UINT256_MAX
    )
    call_and_transact(
        token_network.functions.setTotalWithdraw(
            channel_identifier2, A, withdraw_A, UINT256_MAX, signature_A_for_A2, signature_B_for_A2
        ),
        {"from": A},
    )


def test_withdraw_event(
    token_network: Contract,
    create_channel_and_deposit: Callable,
    get_accounts: Callable,
    withdraw_channel: Callable,
    event_handler: Callable,
) -> None:
    (A, B, C) = get_accounts(3)
    ev_handler = event_handler(token_network)

    channel_identifier = create_channel_and_deposit(A, B, 10, 1)

    txn_hash = withdraw_channel(channel_identifier, A, 5, UINT256_MAX, B)
    ev_handler.add(txn_hash, ChannelEvent.WITHDRAW, check_withdraw(channel_identifier, A, 5))

    txn_hash = withdraw_channel(channel_identifier, B, 2, UINT256_MAX, A, C)
    ev_handler.add(txn_hash, ChannelEvent.WITHDRAW, check_withdraw(channel_identifier, B, 2))

    ev_handler.check()
