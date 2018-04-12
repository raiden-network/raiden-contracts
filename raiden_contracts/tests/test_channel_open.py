import pytest
from ethereum import tester
from raiden_contracts.utils.config import (
    E_CHANNEL_OPENED,
    SETTLE_TIMEOUT_MIN,
    SETTLE_TIMEOUT_MAX
)
from .utils import check_channel_opened
from .fixtures.config import (
    empty_address,
    fake_address,
    fake_bytes
)


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

    channel = token_network.call().getChannelInfo(1)
    assert channel[0] == 0  # settle_block_number
    assert channel[1] == 0  # state

    token_network.transact().openChannel(A, B, settle_timeout)

    channel = token_network.call().getChannelInfo(1)
    assert channel[0] == settle_timeout  # settle_block_number
    assert channel[1] == 1  # state

    A_state = token_network.call().getChannelParticipantInfo(1, A)
    assert A_state[0] == 0
    assert A_state[1] is True
    assert A_state[2] is False
    assert A_state[3] == fake_bytes(32)
    assert A_state[4] == 0

    B_state = token_network.call().getChannelParticipantInfo(1, B)
    assert B_state[0] == 0
    assert B_state[1] is True
    assert B_state[2] is False
    assert B_state[3] == fake_bytes(32)
    assert B_state[4] == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.transact().openChannel(A, B, SETTLE_TIMEOUT_MIN)

    ev_handler.add(txn_hash, E_CHANNEL_OPENED, check_channel_opened(1, A, B, SETTLE_TIMEOUT_MIN))
    ev_handler.check()
