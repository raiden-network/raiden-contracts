import pytest
from eth_tester.exceptions import TransactionFailed
from raiden_contracts.constants import (
    EVENT_CHANNEL_OPENED,
    SETTLE_TIMEOUT_MIN,
    SETTLE_TIMEOUT_MAX,
    CHANNEL_STATE_NONEXISTENT,
    CHANNEL_STATE_OPENED,
)
from raiden_contracts.utils.events import check_channel_opened
from .fixtures.config import empty_address, fake_address, fake_bytes
from web3.exceptions import ValidationError


def test_open_channel_call(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, B, -3).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(0x0, B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel('', B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(fake_address, B, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, 0x0, settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, '', settle_timeout).transact()
    with pytest.raises(ValidationError):
        token_network.functions.openChannel(A, fake_address, settle_timeout).transact()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(empty_address, B, settle_timeout).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, empty_address, settle_timeout).transact()

    # Cannot open a channel between 2 participants with the same address
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, A, settle_timeout).transact()

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, SETTLE_TIMEOUT_MIN - 1).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, SETTLE_TIMEOUT_MAX + 1).transact()


def test_max_1_channel(token_network, get_accounts, create_channel):
    (A, B) = get_accounts(2)
    create_channel(A, B, SETTLE_TIMEOUT_MIN)

    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(A, B, SETTLE_TIMEOUT_MIN).transact()
    with pytest.raises(TransactionFailed):
        token_network.functions.openChannel(B, A, SETTLE_TIMEOUT_MIN).transact()


def test_open_channel_state(token_network, get_accounts):
    (A, B) = get_accounts(2)
    settle_timeout = SETTLE_TIMEOUT_MIN + 10

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == 0
    assert state == CHANNEL_STATE_NONEXISTENT

    token_network.functions.openChannel(A, B, settle_timeout).transact()

    (_, settle_block_number, state) = token_network.functions.getChannelInfo(A, B).call()
    assert settle_block_number == settle_timeout
    assert state == CHANNEL_STATE_OPENED

    (
        A_deposit,
        A_withdrawn,
        A_is_the_closer,
        A_balance_hash,
        A_nonce,
    ) = token_network.functions.getChannelParticipantInfo(A, B).call()
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
        B_nonce,
    ) = token_network.functions.getChannelParticipantInfo(B, A).call()
    assert B_deposit == 0
    assert B_withdrawn == 0
    assert B_is_the_closer is False
    assert B_balance_hash == fake_bytes(32)
    assert B_nonce == 0


def test_open_channel_event(get_accounts, token_network, event_handler):
    ev_handler = event_handler(token_network)
    (A, B) = get_accounts(2)

    txn_hash = token_network.functions.openChannel(A, B, SETTLE_TIMEOUT_MIN).transact()
    channel_identifier = token_network.functions.getChannelIdentifier(A, B).call()

    ev_handler.add(
        txn_hash,
        EVENT_CHANNEL_OPENED,
        check_channel_opened(channel_identifier, A, B, SETTLE_TIMEOUT_MIN),
    )
    ev_handler.check()
