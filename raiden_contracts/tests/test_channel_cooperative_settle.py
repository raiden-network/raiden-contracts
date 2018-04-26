from raiden_contracts.utils.config import (
    E_CHANNEL_SETTLED,
    SETTLE_TIMEOUT_MIN,
    CHANNEL_STATE_OPEN,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED
)
from raiden_contracts.utils.events import check_channel_settled
from .fixtures.config import fake_bytes


def test_cooperative_settle_channel_state(
        web3,
        custom_token,
        token_network,
        create_channel,
        channel_deposit,
        get_accounts,
        get_block,
        create_cooperative_settle_signature
):
    (A, B, C) = get_accounts(3)
    settle_timeout = SETTLE_TIMEOUT_MIN
    deposit_A = 20
    deposit_B = 10
    balance_A = 5
    balance_B = 25

    # Create channel and deposit
    channel_identifier = create_channel(A, B, settle_timeout)
    channel_deposit(channel_identifier, A, deposit_A)
    channel_deposit(channel_identifier, B, deposit_B)

    # Create cooperative settle message
    signature_A = create_cooperative_settle_signature(
        channel_identifier,
        A,
        A, balance_A,
        B, balance_B
    )
    signature_B = create_cooperative_settle_signature(
        channel_identifier,
        B,
        A, balance_A,
        B, balance_B
    )

    pre_account_balance_A = custom_token.call().balanceOf(A)
    pre_account_balance_B = custom_token.call().balanceOf(B)
    pre_balance_contract = custom_token.call().balanceOf(token_network.address)

    # Settle the channel
    token_network.transact({'from': C}).cooperativeSettle(
        channel_identifier,
        A, balance_A,
        B, balance_B,
        signature_A,
        signature_B
    )

    # Make sure the correct amount of tokens has been transferred
    account_balance_A = custom_token.call().balanceOf(A)
    account_balance_B = custom_token.call().balanceOf(B)
    balance_contract = custom_token.call().balanceOf(token_network.address)
    assert account_balance_A == pre_account_balance_A + balance_A
    assert account_balance_B == pre_account_balance_B + balance_B
    assert balance_contract == pre_balance_contract - balance_A - balance_B

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

    # Make sure there is no balance data
    assert A_locksroot == fake_bytes(32)
    assert A_locked_amount == 0

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

    # Make sure there is no balance data
    assert B_locksroot == fake_bytes(32)
    assert B_locked_amount == 0


def test_update_channel_event(
        web3,
        get_accounts,
        token_network,
        create_channel,
        channel_deposit,
        create_cooperative_settle_signature,
        event_handler
):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)
    deposit_A = 10
    balance_A = 2
    balance_B = 8
    channel_identifier = create_channel(A, B)
    channel_deposit(channel_identifier, A, deposit_A)

    signature_A = create_cooperative_settle_signature(
        channel_identifier,
        A,
        B, balance_B,
        A, balance_A
    )
    signature_B = create_cooperative_settle_signature(
        channel_identifier,
        B,
        B, balance_B,
        A, balance_A
    )

    # Settle the channel
    txn_hash = token_network.transact({'from': B}).cooperativeSettle(
        channel_identifier,
        B, balance_B,
        A, balance_A,
        signature_B,
        signature_A
    )

    ev_handler.add(txn_hash, E_CHANNEL_SETTLED, check_channel_settled(channel_identifier))
    ev_handler.check()
