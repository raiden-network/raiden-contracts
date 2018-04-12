from raiden_contracts.utils.config import E_CHANNEL_CLOSED
from .utils import check_channel_closed
from .fixtures.config import (
    fake_bytes
)


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
    channel_identifier = create_channel(A, B, settle_timeout)
    channel_deposit(channel_identifier, A, deposit_A)
    balance_proof = create_balance_proof(
        channel_identifier,
        B,
        transferred_amount,
        0,
        nonce,
        fake_bytes(32, '02')
    )

    channel = token_network.call().getChannelInfo(1)
    assert channel[0] == settle_timeout  # settle_block_number
    assert channel[1] == 1  # state

    A_state = token_network.call().getChannelParticipantInfo(1, A)
    assert A_state[1] is True  # initialized
    assert A_state[2] is False  # is_closer
    assert A_state[3] == fake_bytes(32)  # balance_hash
    assert A_state[4] == 0  # nonce

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof)

    channel = token_network.call().getChannelInfo(1)
    assert channel[0] == settle_timeout + get_block(txn_hash)  # settle_block_number
    assert channel[1] == 2  # state

    A_state = token_network.call().getChannelParticipantInfo(1, A)
    assert A_state[1] is True  # initialized
    assert A_state[2] is True  # is_closer
    assert A_state[3] == fake_bytes(32)  # balance_hash
    assert A_state[4] == 0  # nonce

    B_state = token_network.call().getChannelParticipantInfo(1, B)
    assert B_state[1] is True  # initialized
    assert B_state[2] is False  # is_closer
    assert B_state[3] == balance_proof[2]  # balance_hash
    assert B_state[4] == nonce  # nonce


def test_close_channel_event_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)
    balance_proof = create_balance_proof(channel_identifier, B, 0, 0, 0)

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof)

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

    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)
    balance_proof = create_balance_proof(channel_identifier, B, 5, 0, 3)

    txn_hash = token_network.transact({'from': A}).closeChannel(*balance_proof)

    ev_handler.add(txn_hash, E_CHANNEL_CLOSED, check_channel_closed(channel_identifier, A))
    ev_handler.check()
