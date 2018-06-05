import pytest
from eth_tester.exceptions import TransactionFailed

from raiden_contracts.utils.config import (
    SETTLE_TIMEOUT_MIN,
    E_CHANNEL_CLOSED,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_CLOSED
)
from raiden_contracts.utils.events import check_channel_closed
from .fixtures.config import fake_bytes, fake_hex


def test_close_nonexistent_channel(
        token_network,
        get_accounts
):
    (A, B) = get_accounts(2)

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64)
        ).transact({'from': A})


def test_close_settled_channel(
        web3,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts
):
    (A, B) = get_accounts(2)
    create_channel(A, B, SETTLE_TIMEOUT_MIN)
    channel_deposit(A, 5, B)

    (_, _, state) = token_network.functions.getChannelInfo(A, B).call()
    assert state == CHANNEL_STATE_OPEN

    token_network.functions.closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    ).transact({'from': A})
    web3.testing.mine(SETTLE_TIMEOUT_MIN)
    token_network.functions.settleChannel(
        A,
        0,
        0,
        fake_bytes(32),
        B,
        0,
        0,
        fake_bytes(32)
    ).transact({'from': A})

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED
    assert settle_block_number == 0

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64)
        ).transact({'from': A})


def test_close_wrong_signature(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof
):
    (A, B, C) = get_accounts(3)
    deposit_A = 6
    transferred_amount = 5
    nonce = 3
    locksroot = fake_hex(32, '03')

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        C,
        transferred_amount,
        0,
        nonce,
        locksroot
    )

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(B, *balance_proof).transact({'from': A})


def test_close_call_twice_fail(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts
):
    (A, B) = get_accounts(2)
    create_channel(A, B)
    channel_deposit(A, 5, B)

    token_network.functions.closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    ).transact({'from': A})

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64)
        ).transact({'from': A})


def test_close_wrong_sender(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts
):
    (A, B, C) = get_accounts(3)
    create_channel(A, B)
    channel_deposit(A, 5, B)

    with pytest.raises(TransactionFailed):
        token_network.functions.closeChannel(
            B,
            fake_bytes(32),
            0,
            fake_bytes(32),
            fake_bytes(64)
        ).transact({'from': C})


def test_close_channel_state(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_balance_proof
):
    (A, B) = get_accounts(2)
    settle_timeout = 6
    deposit_A = 20
    transferred_amount = 5
    nonce = 3
    locksroot = fake_hex(32, '03')

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, deposit_A, B)

    # Create balance proofs
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
        transferred_amount,
        0,
        nonce,
        locksroot
    )

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPEN

    (
        _, _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.functions.getChannelParticipantInfo(A, B).call()
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    txn_hash = token_network.functions.closeChannel(B, *balance_proof).transact({'from': A})

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == settle_timeout + get_block(txn_hash)
    assert state == CHANNEL_STATE_CLOSED

    (
        _, _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.functions.getChannelParticipantInfo(A, B).call()
    assert A_is_the_closer is True
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        _, _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce
    ) = token_network.functions.getChannelParticipantInfo(B, A).call()
    assert B_is_the_closer is False
    assert B_balance_hash == balance_proof[0]
    assert B_nonce == nonce


def test_close_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]

    # No off-chain transfers have occured
    # There is no signature data here, because it was never provided to A
    txn_hash = token_network.functions.closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    ).transact({'from': A})

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()


def test_close_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, deposit_A, B)
    balance_proof = create_balance_proof(channel_identifier, B, 5, 0, 3)

    txn_hash = token_network.functions.closeChannel(B, *balance_proof).transact({'from': A})

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
