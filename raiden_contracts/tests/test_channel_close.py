from raiden_contracts.utils.config import (
    E_CHANNEL_CLOSED,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_CLOSED
)
from raiden_contracts.utils.events import check_channel_closed
from .fixtures.config import fake_bytes, fake_hex


def test_close_channel_fail_small_deposit():
    pass


# TODO: test event argument when a delegate closes
def test_close_channel_event_delegate():
    pass


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

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPEN

    (
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.call().getChannelParticipantInfo(A, B)
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    txn_hash = token_network.transact({'from': A}).closeChannel(B, *balance_proof)

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == settle_timeout + get_block(txn_hash)
    assert state == CHANNEL_STATE_CLOSED

    (
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.call().getChannelParticipantInfo(A, B)
    assert A_is_the_closer is True
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce
    ) = token_network.call().getChannelParticipantInfo(B, A)
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
    balance_proof = create_balance_proof(channel_identifier, B, 0, 0, 0)

    txn_hash = token_network.transact({'from': A}).closeChannel(B, *balance_proof)

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

    txn_hash = token_network.transact({'from': A}).closeChannel(B, *balance_proof)

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
