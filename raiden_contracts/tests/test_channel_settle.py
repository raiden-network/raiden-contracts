from raiden_contracts.utils.config import (
    E_CHANNEL_SETTLED,
    SETTLE_TIMEOUT_MIN,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED
)
from raiden_contracts.utils.events import check_channel_settled
from .utils import get_settlement_amounts
from .fixtures.config import fake_hex


def test_settle_no_bp_success(
        web3,
        token_network,
        create_channel_and_deposit,
        get_accounts,
        create_balance_proof
):
    (A, B) = get_accounts(2)
    deposit_A = 10
    deposit_B = 6
    settle_timeout = SETTLE_TIMEOUT_MIN
    locksroot = fake_hex(32, '00')
    additional_hash = fake_hex(32, '00')
    channel_identifier = create_channel_and_deposit(A, B, deposit_A, deposit_B)

    # Create balance proofs
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B, 0, 0, 0,
        locksroot, additional_hash
    )

    # Close channel and update balance proofs
    token_network.transact({'from': A}).closeChannel(*balance_proof_B)

    # Do not call updateNonClosingBalanceProof

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    # Settling the channel should work with no balance proofs
    token_network.transact({'from': A}).settleChannel(
        channel_identifier,
        A, 0, 0, locksroot,
        B, 0, 0, locksroot
    )


def test_settle_channel_state(
        web3,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_balance_proof,
        create_balance_proof_update_signature
):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN
    deposit_A = 20
    additional_hash = fake_hex(32, '02')
    locksroot1 = fake_hex(32, '03')
    locksroot2 = fake_hex(32, '04')

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)
    channel_deposit(channel_identifier, A, deposit_A)

    # Create balance proofs
    balance_proof_A = create_balance_proof(
        channel_identifier,
        A, 10, 2, 5,
        locksroot1, additional_hash
    )
    balance_proof_B = create_balance_proof(
        channel_identifier,
        B, 5, 1, 3,
        locksroot2, additional_hash
    )
    balance_proof_update_signature_B = create_balance_proof_update_signature(B, *balance_proof_A)

    # Close channel and update balance proofs
    token_network.transact({'from': A}).closeChannel(*balance_proof_B)
    token_network.transact({'from': B}).updateNonClosingBalanceProof(
        *balance_proof_A,
        balance_proof_update_signature_B
    )

    # Settlement window must be over before settling the channel
    web3.testing.mine(settle_timeout)

    pre_balance_A = custom_token.call().balanceOf(A)
    pre_balance_B = custom_token.call().balanceOf(B)
    pre_balance_contract = custom_token.call().balanceOf(token_network.address)

    token_network.transact({'from': A}).settleChannel(
        channel_identifier,
        A, 10, 2, locksroot1,
        B, 5, 1, locksroot2
    )

    # Make sure channel data has been removed
    (settle_block_number, state) = token_network.call().getChannelInfo(1)
    assert settle_block_number == 0  # settle_block_number
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED  # state

    # Make sure participant data has been removed
    (
        A_deposit,
        A_is_initialized,
        A_is_the_closer,
        A_locksroot,
        A_locked_amount
    ) = token_network.call().getChannelParticipantInfo(1, A, B)
    assert A_deposit == 0
    assert A_is_initialized == 0
    assert A_is_the_closer == 0

    # Make sure balance data has been updated
    assert A_locksroot == bytearray.fromhex(locksroot1[2:])
    assert A_locked_amount == 2

    (
        B_deposit,
        B_is_initialized,
        B_is_the_closer,
        B_locksroot,
        B_locked_amount
    ) = token_network.call().getChannelParticipantInfo(1, B, A)
    assert B_deposit == 0
    assert B_is_initialized == 0
    assert B_is_the_closer == 0

    # Make sure balance data has been updated
    assert B_locksroot == bytearray.fromhex(locksroot2[2:])
    assert B_locked_amount == 1

    # Make sure the correct amount of tokens has been transferred
    (A_amount, B_amount, locked_amount) = get_settlement_amounts(deposit_A, 10, 2, 0, 5, 1)
    balance_A = custom_token.call().balanceOf(A)
    balance_B = custom_token.call().balanceOf(B)
    balance_contract = custom_token.call().balanceOf(token_network.address)
    assert balance_A == pre_balance_A + A_amount
    assert balance_B == pre_balance_B + B_amount
    assert balance_contract == pre_balance_contract - A_amount - B_amount


def test_update_channel_event(
        web3,
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
    settle_timeout = SETTLE_TIMEOUT_MIN
    locksroot = fake_hex(32, '00')

    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)

    balance_proof_A = create_balance_proof(channel_identifier, A, 10, 0, 1, locksroot)
    balance_proof_B = create_balance_proof(channel_identifier, B, 5, 0, 3, locksroot)
    balance_proof_update_signature_B = create_balance_proof_update_signature(B, *balance_proof_A)

    token_network.transact({'from': A}).closeChannel(*balance_proof_B)
    token_network.transact({'from': B}).updateNonClosingBalanceProof(
        *balance_proof_A,
        balance_proof_update_signature_B
    )

    web3.testing.mine(settle_timeout)
    txn_hash = token_network.transact({'from': A}).settleChannel(
        channel_identifier,
        A, 10, 0, locksroot,
        B, 5, 0, locksroot
    )

    ev_handler.add(txn_hash, E_CHANNEL_SETTLED, check_channel_settled(channel_identifier))
    ev_handler.check()
