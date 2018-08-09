import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.constants import (
    TEST_SETTLE_TIMEOUT_MIN,
    ChannelEvent,
    ChannelState,
)
from raiden_contracts.utils.events import check_channel_closed
from .fixtures.config import fake_bytes, fake_hex
from raiden_contracts.tests.utils import ChannelValues
from raiden_contracts.utils.merkle import EMPTY_MERKLE_ROOT


def test_close_nonexistent_channel(
        token_network,
        get_accounts,
):
    (A, B) = get_accounts(2)
    non_existent_channel_identifier = 1

    (settle_block_number, state) = token_network.functions.getChannelInfo(
        non_existent_channel_identifier,
        A,
        B,
    ).call()
    assert state == ChannelState.NONEXISTENT
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            non_existent_channel_identifier,
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64),
        ).transact({'from': A})


def test_close_settled_channel(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B, TEST_SETTLE_TIMEOUT_MIN)[0]
    channel_deposit(channel_identifier, A, 5, B)

    (_, state) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.OPENED

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier,
        A,
        0,
        0,
        fake_bytes(32),
        B,
        0,
        0,
        fake_bytes(32),
    ).transact({'from': A})

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert state == ChannelState.REMOVED
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64),
        ).transact({'from': A})


def test_close_wrong_signature(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
):
    (A, B, C) = get_accounts(3)
    deposit_A = 6
    transferred_amount = 5
    nonce = 3
    locksroot = fake_hex(32, '03')

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        C,
        transferred_amount,
        0,
        nonce,
        locksroot,
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            *balance_proof,
        ).transact({'from': A})


def test_close_call_twice_fail(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64),
        ).transact({'from': A})


def test_close_wrong_sender(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, 5, B)

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64),
        ).transact({'from': C})


def test_close_first_argument_is_for_partner_transfer(
        token_network,
        create_channel,
        get_accounts,
        create_balance_proof,
):
    (A, B) = get_accounts(2)

    # Create channel
    channel_identifier = create_channel(A, B, settle_timeout=TEST_SETTLE_TIMEOUT_MIN)[0]

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
    )

    # closeChannel fails, if the provided balance proof is from the same participant who closes
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier,
            B,
            *balance_proof,
        ).transact({'from': B})

    # Else, closeChannel works with this balance proof
    token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof,
    ).transact({'from': A})


def test_close_first_participant_can_close(
        token_network,
        create_channel,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})


def test_close_second_participant_can_close(
        token_network,
        create_channel,
        get_accounts,
):
    (A, B) = get_accounts(2)
    channel_identifier = create_channel(A, B)[0]

    token_network.functions.closeChannel(
        channel_identifier,
        A,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': B})


def test_close_channel_state(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_balance_proof,
):
    (A, B) = get_accounts(2)
    settle_timeout = TEST_SETTLE_TIMEOUT_MIN
    deposit_A = 20
    transferred_amount = 5
    nonce = 3
    locksroot = fake_hex(32, '03')

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
        transferred_amount,
        0,
        nonce,
        locksroot,
    )

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
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
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof,
    ).transact({'from': A})

    (
        settle_block_number,
        state,
    ) = token_network.functions.getChannelInfo(channel_identifier, A, B).call()
    assert settle_block_number == settle_timeout + get_block(txn_hash)
    assert state == ChannelState.CLOSED

    (
        _, _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, A, B).call()
    assert A_is_the_closer is True
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce,
        _,
        _,
    ) = token_network.functions.getChannelParticipantInfo(channel_identifier, B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == balance_proof[0]
    assert B_nonce == nonce


def test_close_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]

    # No off-chain transfers have occured
    # There is no signature data here, because it was never provided to A
    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64),
    ).transact({'from': A})

    ev_handler.add(txn_hash, ChannelEvent.CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()


def test_close_replay_reopened_channel(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
):
    (A, B) = get_accounts(2)
    nonce = 3
    values_A = ChannelValues(
        deposit=10,
        transferred=0,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    values_B = ChannelValues(
        deposit=20,
        transferred=15,
        locked=0,
        locksroot=EMPTY_MERKLE_ROOT,
    )
    channel_identifier1 = create_channel(A, B)[0]
    channel_deposit(channel_identifier1, B, values_B.deposit, A)

    balance_proof_B = create_balance_proof(
        channel_identifier1,
        B,
        values_B.transferred,
        values_B.locked,
        nonce,
        values_B.locksroot,
    )
    token_network.functions.closeChannel(
        channel_identifier1,
        B,
        *balance_proof_B,
    ).transact({'from': A})
    web3.testing.mine(TEST_SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        channel_identifier1,
        A,
        values_A.transferred,
        values_A.locked,
        values_A.locksroot,
        B,
        values_B.transferred,
        values_B.locked,
        values_B.locksroot,
    ).transact({'from': A})

    # Reopen the channel and make sure we cannot use the old balance proof
    channel_identifier2 = create_channel(A, B)[0]
    channel_deposit(channel_identifier2, B, values_B.deposit, A)

    assert channel_identifier1 != channel_identifier2
    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            channel_identifier2,
            B,
            *balance_proof_B,
        ).transact({'from': A})

    # Balance proof with correct channel_identifier must work
    balance_proof_B2 = create_balance_proof(
        channel_identifier2,
        B,
        values_B.transferred,
        values_B.locked,
        nonce,
        values_B.locksroot,
    )
    token_network.functions.closeChannel(
        channel_identifier2,
        B,
        *balance_proof_B2,
    ).transact({'from': A})


def test_close_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        event_handler,
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(channel_identifier, A, deposit_A, B)
    balance_proof = create_balance_proof(channel_identifier, B, 5, 0, 3)

    txn_hash = token_network.functions.closeChannel(
        channel_identifier,
        B,
        *balance_proof,
    ).transact({'from': A})

    ev_handler.add(txn_hash, ChannelEvent.CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
