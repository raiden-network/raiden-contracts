from typing import Callable

import pytest
from eth_tester.exceptions import TransactionFailed
from hexbytes import HexBytes
from web3 import Web3
from web3.contract import Contract
from web3.types import Wei

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
    MessageTypeId,
)
from raiden_contracts.tests.utils import (
    EMPTY_ADDITIONAL_HASH,
    EMPTY_BALANCE_HASH,
    EMPTY_SIGNATURE,
    NONEXISTENT_LOCKSROOT,
    ChannelValues,
    LockedAmounts,
    call_and_transact,
    fake_bytes,
)
from raiden_contracts.tests.utils.blockchain import mine_blocks
from raiden_contracts.utils.events import check_channel_closed


def test_close_nonexistent_channel(token_network: Contract, get_accounts: Callable) -> None:
    """ Test getChannelInfo and closeChannel on a not-yet opened channel """
    (A, B) = get_accounts(2)
    non_existent_channel_identifier = 1

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier=non_existent_channel_identifier, participant1=A, participant2=B
    ).call()
    assert state == ChannelState.NONEXISTENT
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier=non_existent_channel_identifier,
            closing_participant=A,
            non_closing_participant=B,
            balance_hash=EMPTY_BALANCE_HASH,
            nonce=0,
            additional_hash=EMPTY_ADDITIONAL_HASH,
            non_closing_signature=EMPTY_SIGNATURE,
            closing_signature=EMPTY_SIGNATURE,
        ).call({"from": A, "gas": Wei(81_000)})


def test_close_settled_channel_fail(
    web3: Web3,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ Test getChannelInfo and closeChannel on an already settled channel """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)[0]
    channel_deposit(channel_identifier, A, 5, B)

    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.OPENED
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
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier,
            participant1=A,
            participant1_transferred_amount=0,
            participant1_locked_amount=0,
            participant1_locksroot=NONEXISTENT_LOCKSROOT,
            participant2=B,
            participant2_transferred_amount=0,
            participant2_locked_amount=0,
            participant2_locksroot=NONEXISTENT_LOCKSROOT,
        ),
        {"from": A},
    )

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert state == ChannelState.REMOVED
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier,
            non_closing_participant=B,
            closing_participant=A,
            balance_hash=EMPTY_BALANCE_HASH,
            nonce=0,
            additional_hash=EMPTY_ADDITIONAL_HASH,
            non_closing_signature=EMPTY_SIGNATURE,
            closing_signature=closing_sig,
        ).call({"from": A})


def test_close_wrong_signature(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ Closing a channel with a balance proof of the third party should fail """
    (A, B, C) = get_accounts(3)
    deposit_A = 6
    transferred_amount = 5
    nonce = 3
    locksroot = fake_bytes(32, "03")

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier, C, transferred_amount, 0, nonce, locksroot
    )
    closing_signature_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof._asdict(),
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof._asdict().values(), closing_signature_A
        ).call({"from": A})


def test_close_call_twice_fail(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ The second of two same closeChannel calls should fail """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)

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

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier,
            non_closing_participant=B,
            closing_participant=A,
            balance_hash=EMPTY_BALANCE_HASH,
            nonce=0,
            additional_hash=EMPTY_ADDITIONAL_HASH,
            non_closing_signature=EMPTY_SIGNATURE,
            closing_signature=closing_sig,
        ).call({"from": A})


def test_close_different_sender(
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ A closeChannel call from a different Ethereum address should succeed """
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)

    token_network.functions.closeChannel(
        channel_identifier=channel_identifier,
        non_closing_participant=B,
        closing_participant=A,
        balance_hash=EMPTY_BALANCE_HASH,
        nonce=0,
        additional_hash=EMPTY_ADDITIONAL_HASH,
        non_closing_signature=EMPTY_SIGNATURE,
        closing_signature=closing_sig,
    ).call({"from": C})


def test_close_nonce_zero(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
    event_handler: Callable,
) -> None:
    """ closeChannel with a balance proof with nonce zero should not change the channel state """
    (A, B) = get_accounts(2)
    vals_B = ChannelValues(
        deposit=20,
        transferred=5,
        locksroot=fake_bytes(32, "03"),
        locked_amounts=LockedAmounts(claimable_locked=3, unclaimable_locked=4),
        nonce=0,
    )
    # Create channel and deposit
    channel_identifier = create_channel(A, B)[0]

    # Create balance proofs
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked_amounts.locked,
        vals_B.nonce,
        vals_B.locksroot,
    )
    close_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )

    (
        _,
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0

    ev_handler = event_handler(token_network)

    close_tx = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), close_sig_A
        ),
        {"from": A},
    )

    ev_handler.add(
        close_tx,
        ChannelEvent.CLOSED,
        check_channel_closed(
            channel_identifier=channel_identifier,
            closing_participant=A,
            nonce=0,
            balance_hash=balance_proof_B.balance_hash,
        ),
    )
    ev_handler.check()

    # Even though we somehow provide valid values for the balance proof, they are not taken into
    # consideration if the nonce is 0.
    # The Raiden client enforces that the nonce is > 0 if off-chain transfers are made.
    (
        _,
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0


def test_close_first_argument_is_for_partner_transfer(
    token_network: Contract,
    create_channel: Callable,
    get_accounts: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ closeChannel fails on a self-submitted balance proof """
    (A, B) = get_accounts(2)

    # Create channel
    channel_identifier = create_channel(A, B, settle_timeout=TEST_SETTLE_TIMEOUT_MIN)[0]

    # Create balance proofs
    balance_proof = create_balance_proof(channel_identifier, B)
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof._asdict(),
    )
    closing_sig_B = create_balance_proof_countersignature(
        participant=B,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof._asdict(),
    )

    # closeChannel fails, if the provided balance proof is from the same participant who closes
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof._asdict().values(), closing_sig_B
        ).call({"from": B})

    # Else, closeChannel works with this balance proof
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )


def test_close_first_participant_can_close(
    token_network: Contract,
    create_channel: Callable,
    get_accounts: Callable,
    get_block: Callable[[HexBytes], int],
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ Simplest successful closeChannel by the first participant """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    closing_sig = create_close_signature_for_no_balance_proof(
        participant=A, channel_identifier=channel_identifier
    )
    close_tx = call_and_transact(
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

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, B, A
    ).call()
    assert settle_block_number == TEST_SETTLE_TIMEOUT_MIN + get_block(close_tx)
    assert state == ChannelState.CLOSED

    (
        _,
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is True
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0

    (
        _,
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0


def test_close_second_participant_can_close(
    token_network: Contract,
    create_channel: Callable,
    get_accounts: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ Simplest successful closeChannel by the second participant """
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    closing_sig = create_close_signature_for_no_balance_proof(B, channel_identifier)

    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier=channel_identifier,
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


def test_close_channel_state(
    web3: Web3,
    custom_token: Contract,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    get_accounts: Callable,
    get_block: Callable,
    create_balance_proof: Callable,
    txn_cost: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ Observe the effect of a successful closeChannel

    This test compares the state of the channel and the balances of Ethereum
    accounts before/after a successful closeChannel call.
    """
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    vals_B = ChannelValues(
        deposit=20,
        transferred=5,
        locksroot=fake_bytes(32, "03"),
        locked_amounts=LockedAmounts(claimable_locked=3, unclaimable_locked=4),
        nonce=3,
    )

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, B, vals_B.deposit, A)

    # Check the state of the openned channel
    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert settle_block_number == settle_timeout
    assert state == ChannelState.OPENED

    (
        _,
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is False
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0
    (
        _,
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == EMPTY_BALANCE_HASH
    assert B_nonce == 0

    pre_eth_balance_A = web3.eth.getBalance(A)
    pre_eth_balance_B = web3.eth.getBalance(B)
    pre_eth_balance_contract = web3.eth.getBalance(token_network.address)
    pre_balance_A = custom_token.functions.balanceOf(A).call()
    pre_balance_B = custom_token.functions.balanceOf(B).call()
    pre_balance_contract = custom_token.functions.balanceOf(token_network.address).call()

    # Create a balance proof
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B,
        vals_B.transferred,
        vals_B.locked_amounts.locked,
        vals_B.nonce,
        vals_B.locksroot,
    )
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )

    txn_hash = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )

    # Test that no balances have changed.
    # There are no transfers to be made in closeChannel.
    assert web3.eth.getBalance(A) == pre_eth_balance_A - txn_cost(txn_hash)
    assert web3.eth.getBalance(B) == pre_eth_balance_B
    assert web3.eth.getBalance(token_network.address) == pre_eth_balance_contract
    assert custom_token.functions.balanceOf(A).call() == pre_balance_A
    assert custom_token.functions.balanceOf(B).call() == pre_balance_B
    assert custom_token.functions.balanceOf(token_network.address).call() == pre_balance_contract

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        channel_identifier, A, B
    ).call()
    assert settle_block_number == settle_timeout + get_block(txn_hash)
    assert state == ChannelState.CLOSED

    (
        _,
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is True
    assert A_balance_hash == EMPTY_BALANCE_HASH
    assert A_nonce == 0

    (
        _,
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == balance_proof_B.balance_hash
    assert B_nonce == vals_B.nonce


def test_close_channel_event_no_offchain_transfers(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    event_handler: Callable,
    create_close_signature_for_no_balance_proof: Callable,
) -> None:
    """ closeChannel succeeds and emits an event even with nonce 0 and no balance proofs """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]
    closing_sig = create_close_signature_for_no_balance_proof(A, channel_identifier)

    # No off-chain transfers have occured
    # There is no signature data here, because it was never provided to A
    txn_hash = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            A,
            EMPTY_BALANCE_HASH,
            0,
            EMPTY_ADDITIONAL_HASH,
            EMPTY_SIGNATURE,
            closing_sig,
        ),
        {"from": A},
    )

    ev_handler.add(
        txn_hash,
        ChannelEvent.CLOSED,
        check_channel_closed(
            channel_identifier=channel_identifier,
            closing_participant=A,
            nonce=0,
            balance_hash=EMPTY_BALANCE_HASH,
        ),
    )
    ev_handler.check()


def test_close_replay_reopened_channel(
    web3: Web3,
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ The same balance proof cannot close another channel between the same participants """
    (A, B) = get_accounts(2)
    nonce = 3
    values_A = ChannelValues(deposit=10, transferred=0)
    values_B = ChannelValues(deposit=20, transferred=15)
    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, B, values_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier1,
        B,
        values_B.transferred,
        values_B.locked_amounts.locked,
        nonce,
        values_B.locksroot,
    )
    closing_sig_A = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier1,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B._asdict(),
    )
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier1, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ),
        {"from": A},
    )
    mine_blocks(web3, TEST_SETTLE_TIMEOUT_MIN + 1)
    call_and_transact(
        token_network.functions.settleChannel(
            channel_identifier=channel_identifier1,
            participant1=A,
            participant1_transferred_amount=values_A.transferred,
            participant1_locked_amount=values_A.locked_amounts.locked,
            participant1_locksroot=values_A.locksroot,
            participant2=B,
            participant2_transferred_amount=values_B.transferred,
            participant2_locked_amount=values_B.locked_amounts.locked,
            participant2_locksroot=values_B.locksroot,
        ),
        {"from": A},
    )

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier2, B, A, *balance_proof_B._asdict().values(), closing_sig_A
        ).call({"from": A})

    # Balance proof with correct channel_identifier must work
    balance_proof_B2 = create_balance_proof(
        channel_identifier2,
        B,
        values_B.transferred,
        values_B.locked_amounts.locked,
        nonce,
        values_B.locksroot,
    )
    closing_sig_A2 = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier2,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof_B2._asdict(),
    )
    call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier2, B, A, *balance_proof_B2._asdict().values(), closing_sig_A2
        ),
        {"from": A},
    )


def test_close_channel_event(
    get_accounts: Callable,
    token_network: Contract,
    create_channel: Callable,
    channel_deposit: Callable,
    create_balance_proof: Callable,
    event_handler: Callable,
    create_balance_proof_countersignature: Callable,
) -> None:
    """ A successful closeChannel call produces a CLOSED event """
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof = create_balance_proof(
        channel_identifier, B, transferred_amount=5, locked_amount=0, nonce=3
    )
    close_sig = create_balance_proof_countersignature(
        participant=A,
        channel_identifier=channel_identifier,
        msg_type=MessageTypeId.BALANCE_PROOF,
        **balance_proof._asdict(),
    )

    txn_hash = call_and_transact(
        token_network.functions.closeChannel(
            channel_identifier, B, A, *balance_proof._asdict().values(), close_sig
        ),
        {"from": A},
    )

    ev_handler.add(
        txn_hash,
        ChannelEvent.CLOSED,
        check_channel_closed(
            channel_identifier=channel_identifier,
            closing_participant=A,
            nonce=3,
            balance_hash=balance_proof.balance_hash,
        ),
    )
    ev_handler.check()
