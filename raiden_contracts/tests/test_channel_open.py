import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.utils.config import (
    E_CHANNEL_OPENED,
    SETTLE_TIMEOUT_MIN,
    SETTLE_TIMEOUT_MAX,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED,
    CHANNEL_STATE_OPEN
)
from raiden_contracts.utils.events import check_channel_opened
from .fixtures.config import empty_address, fake_address, fake_bytes
from web3.exceptions import ValidationError


def test_open_channel_call(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(A, B, -3)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(0x0, B, settle_timeout)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel('', B, settle_timeout)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(fake_address, B, settle_timeout)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(A, 0x0, settle_timeout)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(A, '', settle_timeout)
    with pytest.raises(ValidationError):
        token_network.transact().openChannel(A, fake_address, settle_timeout)

    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(empty_address, B, settle_timeout)
    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(A, empty_address, settle_timeout)

    # Cannot open a channel between 2 participants with the same address
    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(A, A, settle_timeout)

    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN - 1)
    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MAX + 1)


def test_max_1_channel(token_network, get_accounts, create_channel):
    (A, B) = get_accounts(2)
    create_channel(A, B, SETTLE_TIMEOUT_MIN)

    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN)
    with pytest.raises(TransactionFailed):
        token_network.transact().openChannel(B, A, SETTLE_TIMEOUT_MIN)


def test_open_channel_state(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == 0
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED

    token_network.transact().openChannel(A, B, settle_timeout)

    (_, settle_block_number, state) = token_network.call().getChannelInfo(A, B)
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPEN

    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.call().getChannelParticipantInfo(A, B)
    assert A_deposit == 0
    assert A_withdrawn == 0
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        B_deposit,
        B_withdrawn,
        B_is_the_closer,
        B_balance_hash,
        B_nonce
    ) = token_network.call().getChannelParticipantInfo(B, A)
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN)
    channel_identifier = token_network.call().getChannelIdentifier(A, B)

    ev_handler.add(
        txn_hash,
        E_CHANNEL_OPENED,
        check_channel_opened(channel_identifier, A, B, SETTLE_TIMEOUT_MIN)
    )
    ev_handler.check()
