import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.utils.config import (
    E_TRANSFER_UPDATED,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_CLOSED,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED
)
from raiden_contracts.utils.events import check_transfer_updated
from .fixtures.config import fake_bytes, empty_address


def test_update_call(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, 15, B)
    token_network.transact({'from': A}).closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    )

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )
    (balance_hash, nonce, additional_hash, closing_signature) = balance_proof_A

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            empty_address, B,
            *balance_proof_A,
            balance_proof_update_signature_B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, empty_address,
            *balance_proof_A,
            balance_proof_update_signature_B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A,
            fake_bytes(64)
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            fake_bytes(32),
            nonce,
            additional_hash,
            closing_signature,
            balance_proof_update_signature_B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            balance_hash,
            0,
            additional_hash,
            closing_signature,
            balance_proof_update_signature_B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            balance_hash,
            nonce,
            additional_hash,
            fake_bytes(64),
            balance_proof_update_signature_B
        )


def test_update_nonexistent_fail(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B, C) = get_accounts(3)

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == 0
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED

    channel_identifier = token_network.call().getChannelIdentifier(A, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A,
            balance_proof_update_signature_B
        )


def test_update_notclosed_fail(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number > 0
    assert state == CHANNEL_STATE_OPEN

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A,
            balance_proof_update_signature_B
        )


def test_update_wrong_signatures(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B, C) = get_accounts(3)
    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, 25, B)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_A_fake = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'), signer=C)

    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )
    balance_proof_update_signature_B_fake = create_balance_proof_update_signature(
        C,
        channel_identifier,
        *balance_proof_A
    )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A_fake,
            balance_proof_update_signature_B
        )
    with pytest.raises(TransactionFailed):
        token_network.transact({'from': C}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A,
            balance_proof_update_signature_B_fake
        )


def test_update_channel_state(
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B, Delegate) = get_accounts(3)
    settle_timeout = 6
    deposit_A = 20
    channel_identifier = create_channel(A, B, settle_timeout)[0]
    channel_deposit(A, deposit_A, B)
    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 5, fake_bytes(32, '02'))
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, fake_bytes(32, '02'))
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    txn_hash1 = token_network.transact({'from': A}).closeChannel(B, *balance_proof_B)

    token_network.transact({'from': Delegate}).updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B
    )

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == settle_timeout + get_block(txn_hash1)  # settle_block_number
    assert state == CHANNEL_STATE_CLOSED  # state

    (
        _,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.call().getChannelParticipantInfo(A, B)
    assert A_is_the_closer is True
    assert A_balance_hash == balance_proof_A[0]
    assert A_nonce == 5

    (
        _,
        B_is_the_closer,
        B_balance_hash,
        B_nonce
    ) = token_network.call().getChannelParticipantInfo(B, A)
    assert B_is_the_closer is False
    assert B_balance_hash == balance_proof_B[0]
    assert B_nonce == 3


def test_update_channel_fail_no_offchain_transfers(
        get_accounts,
        token_network,
        create_channel,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B) = get_accounts(2)

    channel_identifier = create_channel(A, B)[0]
    balance_proof_A = create_balance_proof(channel_identifier, A, 0, 0, 0)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    token_network.transact({'from': A}).closeChannel(
        B,
        fake_bytes(32),
        0,
        fake_bytes(32),
        fake_bytes(64)
    )

    with pytest.raises(TransactionFailed):
        token_network.transact({'from': B}).updateNonClosingBalanceProof(
            A, B,
            *balance_proof_A,
            balance_proof_update_signature_B
        )


def test_update_channel_event(
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_balance_proof,
        create_balance_proof_update_signature,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 10

    channel_identifier = create_channel(A, B)[0]
    channel_deposit(A, deposit_A, B)
    channel_deposit(B, deposit_B, A)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3)
    balance_proof_A = create_balance_proof(channel_identifier, A, 2, 0, 1)
    balance_proof_update_signature_B = create_balance_proof_update_signature(
        B,
        channel_identifier,
        *balance_proof_A
    )

    token_network.transact({'from': A}).closeChannel(B, *balance_proof_B)
    txn_hash = token_network.transact({'from': B}).updateNonClosingBalanceProof(
        A, B,
        *balance_proof_A,
        balance_proof_update_signature_B
    )

    ev_handler.add(txn_hash, E_TRANSFER_UPDATED, check_transfer_updated(channel_identifier, A))
    ev_handler.check()
