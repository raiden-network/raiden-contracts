import pytest
from ethereum import tester
from raiden_contracts.utils.config import E_TRANSFER_UPDATED
from .utils import check_transfer_updated
from .fixtures.config import (
    fake_bytes
)


def test_update_channel_state(
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
    channel_identifier = create_channel(A, B, settle_timeout)
    channel_deposit(channel_identifier, A, deposit_A)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))
    balance_proof_BA = create_balance_proof(channel_identifier, B, 10, 0, 5, fake_bytes(32, '02'))

    txn_hash1 = token_network.transact({'from': A}).closeChannel(*balance_proof_B)

    token_network.transact({'from': B}).updateTransfer(*balance_proof_A, balance_proof_BA[3])

    channel = token_network.call().getChannelInfo(1)
    assert channel[0] == settle_timeout + get_block(txn_hash1)  # settle_block_number
    assert channel[1] == 2  # state

    A_state = token_network.call().getChannelParticipantInfo(1, A)
    assert A_state[1] is True  # initialized
    assert A_state[2] is True  # is_closer
    assert A_state[3] == balance_proof_A[2]  # balance_hash
    assert A_state[4] == 5  # nonce

    B_state = token_network.call().getChannelParticipantInfo(1, B)
    assert B_state[1] is True  # initialized
    assert B_state[2] is False  # is_closer
    assert B_state[3] == balance_proof_B[2]  # balance_hash
    assert B_state[4] == 3


def test_update_channel_fail_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof
):
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)
    balance_proof_B = create_balance_proof(channel_identifier, B, 0, 0, 0)
    balance_proof_A = create_balance_proof(channel_identifier, A, 0, 0, 0)
    balance_proof_BA = create_balance_proof(channel_identifier, B, 0, 0, 0)

    token_network.transact({'from': A}).closeChannel(*balance_proof_B)

    with pytest.raises(tester.TransactionFailed):
        token_network.transact({'from': B}).updateTransfer(*balance_proof_A, balance_proof_BA[3])


def test_update_channel_event(
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
    deposit_B = 10

    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)
    channel_deposit(channel_identifier, B, deposit_B)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3)
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 1)
    balance_proof_AB = create_balance_proof(channel_identifier, B, 2, 0, 1)

    token_network.transact({'from': A}).closeChannel(*balance_proof_B)
    txn_hash = token_network.transact({'from': B}).updateTransfer(
        *balance_proof_A,
        balance_proof_AB[3]
    )

    ev_handler.add(txn_hash, E_TRANSFER_UPDATED, check_transfer_updated(channel_identifier, A))
    ev_handler.check()
