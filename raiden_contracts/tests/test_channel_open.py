import pytest
from ethereum import tester
from raiden_contracts.utils.config import (
    E_CHANNEL_OPENED,
    SETTLE_TIMEOUT_MIN,
    SETTLE_TIMEOUT_MAX,
    CHANNEL_STATE_NONEXISTENT_OR_SETTLED,
    CHANNEL_STATE_OPEN
)
from raiden_contracts.utils.events import check_channel_opened
from .fixtures.config import empty_address, fake_address, fake_bytes


def test_open_channel_call(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10
    with pytest.raises(TypeError):
        token_network.transact().openChannel(A, B, -3)
    with pytest.raises(TypeError):
        token_network.transact().openChannel(0x0, B, settle_timeout)
    with pytest.raises(TypeError):
        token_network.transact().openChannel('', B, settle_timeout)
    with pytest.raises(TypeError):
        token_network.transact().openChannel(fake_address, B, settle_timeout)
    with pytest.raises(TypeError):
        token_network.transact().openChannel(A, 0x0, settle_timeout)
    with pytest.raises(TypeError):
        token_network.transact().openChannel(A, '', settle_timeout)
    with pytest.raises(TypeError):
        token_network.transact().openChannel(A, fake_address, settle_timeout)

    with pytest.raises(tester.TransactionFailed):
        token_network.transact().openChannel(empty_address, B, settle_timeout)
    with pytest.raises(tester.TransactionFailed):
        token_network.transact().openChannel(A, empty_address, settle_timeout)

    # Cannot open a channel between 2 participants with the same address
    with pytest.raises(tester.TransactionFailed):
        token_network.transact().openChannel(A, A, settle_timeout)

    with pytest.raises(tester.TransactionFailed):
        token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN - 1)
    with pytest.raises(tester.TransactionFailed):
        token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MAX + 1)


def test_open_channel_index(token_network, get_accounts):
    (A, B, C, D) = get_accounts(4)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10

    assert token_network.call().last_channel_index() == 0

    for i in range(1, 10):
        token_network.transact().openChannel(A, B, settle_timeout)
        assert token_network.call().last_channel_index() == i


def test_open_channel_state(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10

    (settle_block_number, state) = token_network.call().getChannelInfo(1)
    assert settle_block_number == 0  # settle_block_number
    assert state == CHANNEL_STATE_NONEXISTENT_OR_SETTLED  # state

    token_network.transact().openChannel(A, B, settle_timeout)

    (settle_block_number, state) = token_network.call().getChannelInfo(1)
    assert settle_block_number == settle_timeout  # settle_block_number
    assert state == CHANNEL_STATE_OPEN  # state

    (
        A_deposit,
        A_is_initialized,
        A_is_the_closer,
        A_balance_hash,
        A_nonce
    ) = token_network.call().getChannelParticipantInfo(1, A, B)
    assert A_deposit == 0
    assert A_is_initialized is True
    assert A_is_the_closer is False
    assert A_balance_hash == fake_bytes(32)
    assert A_nonce == 0

    (
        B_deposit,
        B_is_initialized,
        B_is_the_closer,
        B_balance_hash,
        B_nonce
    ) = token_network.call().getChannelParticipantInfo(1, B, A)
    assert B_deposit == 0
    assert B_is_initialized is True
    assert B_is_the_closer is False
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN)

    ev_handler.add(txn_hash, E_CHANNEL_OPENED, check_channel_opened(1, A, B, SETTLE_TIMEOUT_MIN))
    ev_handler.check()
